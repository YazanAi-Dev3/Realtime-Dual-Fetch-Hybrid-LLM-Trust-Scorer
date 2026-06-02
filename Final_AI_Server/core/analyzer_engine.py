import re
import json
import time
import datetime
import requests
import tldextract
import whois
from urllib.parse import urljoin, urlparse, unquote
from bs4 import BeautifulSoup

import google.generativeai as genai
from firecrawl import FirecrawlApp

# Import configurations and logger
from config import GEMINI_API_KEY, FIRECRAWL_API_KEY
from logger_config import logger

# Initialize AI and Scraper clients
genai.configure(api_key=GEMINI_API_KEY)
# We will initialize FirecrawlApp inside the function to avoid global scope issues

# Constants
REQUEST_TIMEOUT = 15
MAX_SUBPAGES = 5
GEMINI_MODEL = 'gemini-flash-lite-latest' 

POLICY_KEYWORDS = ['privacy', 'refund', 'return', 'terms', 'about', 'contact', 'policy', 'سياسة', 'الخصوصية', 'الاسترداد', 'تواصل', 'عن', 'اتصل', 'شروط', 'ضمان', 'معلومات']
GENERIC_POLICY_PATHS = ['/privacy-policy', '/refund-policy', '/return-policy', '/terms', '/contact', '/سياسة-الخصوصية', '/سياسة-الاسترداد', '/ar/return-policy']

DEFAULT_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'ar,en;q=0.9',
}

# Regex Patterns (Saudi Context)
PHONE_PATTERN = re.compile(r'(?:\+966|00966)[ \-]?(?:5[0-9]{8}|9200[0-9]{5})|05[0-9]{8}|9200[0-9]{5}')
EMAIL_PATTERN = re.compile(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.(?!png|jpe?g|gif|svg|webp|avif)[a-zA-Z]{2,}', re.IGNORECASE)
VAT_PATTERN = re.compile(r'\b3[0-9]{14}\b')
CR_PATTERN = re.compile(r'\b(?:10|11|20|40|50)[0-9]{8}\b')

# 1. OSINT & DISCOVERY
def get_whois_info(url: str) -> str:
    ext = tldextract.extract(url)
    root_domain = f"{ext.domain}.{ext.suffix}"
    logger.info(f"Fetching WHOIS for: {root_domain}")
    try:
        w = whois.whois(root_domain)
        c_date = w.creation_date
        if isinstance(c_date, list): c_date = c_date[0]
        if c_date:
            return f"Domain: {root_domain} | Registered: {c_date.strftime('%Y-%m-%d')}"
    except Exception as e:
        logger.warning(f"WHOIS failed: {e}")
    return None

def discover_links(homepage_url: str) -> list:
    logger.info("Starting link discovery...")
    base_url = f"{urlparse(homepage_url).scheme}://{urlparse(homepage_url).netloc}"
    candidates = [{'url': urljoin(base_url, p), 'source': 'known_path', 'relevance': 2} for p in GENERIC_POLICY_PATHS]
    
    try:
        response = requests.get(homepage_url, headers=DEFAULT_HEADERS, timeout=REQUEST_TIMEOUT)
        clean_html = response.text.replace('\\/', '/')
        all_urls = re.findall(r'https?://[a-zA-Z0-9.\-]+/[a-zA-Z0-9.\-/%_]+', clean_html)
        
        for u in set(all_urls):
            if urlparse(homepage_url).netloc in u and any(kw in unquote(u).lower() for kw in POLICY_KEYWORDS):
                candidates.append({'url': u, 'source': 'json_state', 'relevance': 3})
                
    except Exception as e:
        logger.error(f"Link discovery error: {e}")

    # Deduplicate and sort by relevance
    seen, unique_candidates = set(), []
    for c in sorted(candidates, key=lambda k: k['relevance'], reverse=True):
        if c['url'] not in seen:
            seen.add(c['url'])
            unique_candidates.append(c)
            
    return unique_candidates[:MAX_SUBPAGES]

# 2. DUAL-FETCH SCRAPER
def extract_hidden_json_state(html_content: str) -> str:
    if not html_content: return ""
    soup = BeautifulSoup(html_content, 'html.parser')
    hidden_data = [script.get_text(strip=True) for script in soup.find_all('script')]
    return " ".join(hidden_data)

def scrape_pages(candidate_urls: list) -> dict:
    logger.info(f"Scraping {len(candidate_urls)} pages (Dual-Fetch Mode)")
    page_contents = {}
    try:
        app = FirecrawlApp(api_key=FIRECRAWL_API_KEY)
    except Exception as e:
        logger.critical(f"Firecrawl initialization failed: {e}")
        return page_contents

    for candidate in candidate_urls:
        url = candidate['url']
        entry = {'url': url, 'regex_text': '', 'llm_text': ''}
        try:
            # Fetch 1: Raw Requests for JSON Scripts
            raw_resp = requests.get(url, headers=DEFAULT_HEADERS, timeout=REQUEST_TIMEOUT)
            hidden_scripts = extract_hidden_json_state(raw_resp.text)
            
            # Fetch 2: Firecrawl for clean Markdown
            fc_result = app.scrape(url, formats=['markdown'])
            md_text = getattr(fc_result, 'markdown', '') if not isinstance(fc_result, dict) else fc_result.get('markdown', '')
            clean_md = re.sub(r'https?://[^\s",]+', '', md_text)
            
            entry['regex_text'] = clean_md + " \n --- HIDDEN STATE --- \n " + hidden_scripts
            entry['llm_text'] = clean_md                           
            logger.info(f"Successfully fetched: {url}")
        except Exception as e:
            logger.error(f"Failed to fetch {url}: {e}")
            
        page_contents[url] = entry
    return page_contents

# 3. EXTRACTION (REGEX + GEMINI)
def regex_extract(page_contents: dict) -> dict:
    logger.info("Starting Regex extraction...")
    ext = {k: [] for k in ['phone', 'email', 'vat_number', 'commercial_reg']}
    for page in page_contents.values():
        text = page.get('regex_text', '')
        if not text: continue
        safe_text = re.sub(r'https?://[^\s",]+', '', text) 
        
        for m in PHONE_PATTERN.findall(text): 
            if m not in ext['phone']: ext['phone'].append(m)
        for m in EMAIL_PATTERN.findall(text): 
            if m.upper() not in ext['email']: ext['email'].append(m.upper())
        for m in VAT_PATTERN.findall(text): 
            if m not in ext['vat_number']: ext['vat_number'].append(m)
        for m in CR_PATTERN.findall(safe_text): 
            if not str(m).endswith('00000') and m not in ext['commercial_reg']: ext['commercial_reg'].append(m)
    return ext

def gemini_extract(page_contents: dict) -> dict:
    logger.info("Sending clean text to Gemini...")
    prompt = """
    You are a Saudi e-commerce trust analyst. Read the provided pages content.
    Return ONLY valid JSON:
    {
      "privacy_policy": {"exists": true/false, "summary": "brief summary in Arabic"},
      "refund_policy": {"exists": true/false, "summary": "brief summary in Arabic"}
    }
    """
    valid_texts = [f"--- URL: {url} ---\n{page.get('llm_text', '')[:30000]}" for url, page in page_contents.items() if len(page.get('llm_text', '')) > 50]
    combined_text = "\n".join(valid_texts)
    
    if len(combined_text) < 100: return {}
    
    try:
        model = genai.GenerativeModel(GEMINI_MODEL)
        resp = model.generate_content(f"{prompt}\n\nDATA:\n{combined_text}")
        cleaned = re.sub(r'^```json\s*|^```\s*|\s*```$', '', resp.text, flags=re.MULTILINE).strip()
        return json.loads(cleaned)
    except Exception as e:
        logger.error(f"Gemini generation error: {e}")
        return {}

# 4. SCORING ENGINE
def calculate_trust_score(regex_data: dict, gemini_data: dict, domain_info: str) -> dict:
    logger.info("Calculating final trust score...")
    breakdown = {'legal_identity': 0, 'domain_longevity': 0, 'contactability': 0, 'transparency': 0, 'penalties': 0}
    warnings = []
    
    has_cr = len(regex_data.get('commercial_reg', [])) > 0
    has_vat = len(regex_data.get('vat_number', [])) > 0
    if has_cr and has_vat: breakdown['legal_identity'] = 40
    elif has_cr or has_vat:
        breakdown['legal_identity'] = 25
        warnings.append("Partial legal identity found (Missing CR or VAT).")
        
    domain_age_years = 0
    if domain_info:
        match = re.search(r'Registered:\s*(\d{4}-\d{2}-\d{2})', domain_info)
        if match:
            try:
                reg_date = datetime.datetime.strptime(match.group(1), '%Y-%m-%d')
                domain_age_years = (datetime.datetime.now() - reg_date).days / 365.25
                if domain_age_years >= 3.0: breakdown['domain_longevity'] = 25
                elif domain_age_years >= 1.0: breakdown['domain_longevity'] = 15
                elif domain_age_years >= 0.5: breakdown['domain_longevity'] = 10
                else:
                    warnings.append("Domain is very new (less than 6 months old).")
            except: pass
            
    has_phone = len(regex_data.get('phone', [])) > 0
    has_email = len(regex_data.get('email', [])) > 0
    if has_phone and has_email: breakdown['contactability'] = 15
    elif has_phone: breakdown['contactability'] = 12 
    elif has_email: breakdown['contactability'] = 5
    else: warnings.append("No direct contact methods found.")
        
    if gemini_data.get('privacy_policy', {}).get('exists'): breakdown['transparency'] += 10
    if gemini_data.get('refund_policy', {}).get('exists'): breakdown['transparency'] += 10
    
    if domain_age_years < 1.0 and not has_cr and not has_phone:
        breakdown['penalties'] -= 40
        warnings.append("CRITICAL RED FLAG: Ghost Syndrome (New domain, no legal ID, no phone).")

    total_score = max(0, min(100, sum(v for k, v in breakdown.items() if k != 'penalties') + breakdown['penalties']))
    
    if total_score >= 85: tier, color = "Trusted & Secure", "Green"
    elif total_score >= 60: tier, color = "Proceed with Caution", "Yellow"
    else: tier, color = "High Risk / Suspicious", "Red"
        
    return {
        'total_score': total_score,
        'tier': tier,
        'color_code': color,
        'breakdown': breakdown,
        'warnings': warnings,
        'domain_age_years': round(domain_age_years, 1)
    }

# 5. MAIN PIPELINE ORCHESTRATOR
def run_trust_pipeline(url: str) -> dict:
    """The main entry point for the Analyzer API"""
    logger.info(f"=== Starting Analysis Pipeline for {url} ===")
    try:
        domain_info = get_whois_info(url)
        candidates = discover_links(url)
        page_contents = scrape_pages(candidates)
        
        regex_result = regex_extract(page_contents)
        gemini_result = gemini_extract(page_contents)
        
        scoring = calculate_trust_score(regex_result, gemini_result, domain_info)
        
        logger.info(f"Pipeline finished successfully. Score: {scoring['total_score']}")
        
        return {
            "status": "success",
            "url": url,
            "domain_info": domain_info,
            "extracted_data": {
                "regex_matches": regex_result,
                "ai_analysis": gemini_result
            },
            "trust_evaluation": scoring
        }
    except Exception as e:
        logger.critical(f"Pipeline crashed: {e}")
        return {"status": "error", "message": str(e)}