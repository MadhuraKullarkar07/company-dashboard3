from http.server import HTTPServer, SimpleHTTPRequestHandler
import json
import requests
from bs4 import BeautifulSoup
import re
import time
from groq import Groq

# ==========================================
client = Groq(api_key="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")
# ==========================================

results_store = []

def clean_text(text):
    if not text: return ""
    return re.sub(r'\s+', ' ', text).strip()

def extract_emails(text):
    pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    return list(set(re.findall(pattern, text)))

def extract_phones(text):
    patterns = [r'\+\d{1,3}[-.\s]?\d{7,14}', r'\d{3}[-.\s]?\d{3}[-.\s]?\d{4}']
    phones = []
    for p in patterns:
        phones.extend(re.findall(p, text))
    return list(set(phones))[:2]

def process_url(url):
    print(f"Processing: {url}")
    headers = {'User-Agent': 'Mozilla/5.0 Chrome/120.0.0.0'}
    
    text = ""
    try:
        time.sleep(1)
        r = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(r.text, 'html.parser')
        for tag in soup.find_all(['nav', 'footer', 'script', 'style']):
            tag.decompose()
        text = clean_text(soup.get_text(separator=' ', strip=True))
    except Exception as e:
        print(f"Scrape error: {e}")
    
    emails = extract_emails(text)
    phones = extract_phones(text)
    domain = url.split('//')[-1].split('/')[0].replace('www.', '')
    
    result = {
        "website_name": domain,
        "company_name": domain.split('.')[0].capitalize(),
        "address": "N/A",
        "mobile_number": phones[0] if phones else "N/A",
        "mail": emails if emails else [],
        "core_service": "N/A",
        "target_customer": "N/A",
        "probable_pain_point": "N/A",
        "outreach_opener": "N/A"
    }
    
    try:
        print("  Calling Groq AI...")
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": "Return ONLY valid JSON. No other text."},
                {"role": "user", "content": f"Extract business info from text. Return ONLY JSON:\n\n{text[:2000]}\n\nFormat: {{\"website_name\":\"\",\"company_name\":\"\",\"address\":\"\",\"mobile_number\":\"\",\"mail\":[],\"core_service\":\"\",\"target_customer\":\"\",\"probable_pain_point\":\"\",\"outreach_opener\":\"\"}}"}
            ],
            temperature=0.1
        )
        ai_text = response.choices[0].message.content.strip()
        if ai_text.startswith('```'): ai_text = ai_text.split('\n',1)[1]
        if ai_text.endswith('```'): ai_text = ai_text[:-3]
        ai_result = json.loads(ai_text)
        for key in result:
            if key in ai_result and ai_result[key] and ai_result[key] != "N/A":
                result[key] = ai_result[key]
    except Exception as e:
        print(f"  AI Error: {e}")
    
    if emails: result['mail'] = emails
    if phones: result['mobile_number'] = phones[0]
    return result

class Handler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/results':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(results_store).encode())
        elif self.path in ['/', '/index.html']:
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.end_headers()
            with open('templates/index.html', 'r', encoding='utf-8') as f:
                self.wfile.write(f.read().encode())
        else:
            super().do_GET()
    
    def do_POST(self):
        length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(length) if length else b'{}'
        data = json.loads(body)
        
        if self.path == '/enrich':
            result = process_url(data.get('url', ''))
            results_store.append(result)
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(result).encode())
        
        elif self.path == '/preload':
            results_store.clear()
            for u in ["https://www.stripe.com", "https://www.shopify.com", "https://www.twilio.com"]:
                results_store.append(process_url(u))
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({'count': len(results_store)}).encode())
    
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

print("Server running at http://localhost:5000")
print("Developed by Madhura Kullarkar")
HTTPServer(('0.0.0.0', 5000), Handler).serve_forever()
    