import requests
from bs4 import BeautifulSoup
from urllib.parse import quote
import time, csv

# Parameters
keyword = "intern"
location = "United States"
geoId = "103644278"  # LinkedIn's geoId for United States&#8203;:contentReference[oaicite:9]{index=9}

# Construct the LinkedIn jobs search URL (using the unofficial jobs-guest API endpoint)
# We'll URL-encode the keyword and location to be safe.
search_url = ("https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
              f"?keywords={quote(keyword)}&location={quote(location)}&geoId={geoId}&start={{}}")

# Initialize an HTTP session for efficiency and set a user-agent to avoid blocking
session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36"
})

jobs_data = []  # List to collect cleaned job postings

start = 0
while True:
    url = search_url.format(start)
    try:
        resp = session.get(url, timeout=10)
    except requests.RequestException as e:
        print(f"Error fetching jobs page {start}: {e}")
        break
    # If rate-limited or non-200 status, handle or break out
    if resp.status_code == 429:
        print("Rate limit reached. Sleeping for 30 seconds...")
        time.sleep(30)
        continue  # retry the same page after waiting
    if resp.status_code != 200:
        print(f"Failed to retrieve jobs page (status code {resp.status_code}). Stopping.")
        break

    soup = BeautifulSoup(resp.text, 'html.parser')
    job_cards = soup.find_all('li')  # each job posting is in an <li> element
    if not job_cards:
        # No results on this page, end of listings
        break

    for card in job_cards:
        # Each job card container with necessary info
        base_card = card.find('div', class_='base-card')
        if not base_card:
            continue  # skip if structure is unexpected

        # Extract the Job ID from the data-entity-urn (e.g., "urn:li:jobPosting:123456789")
        urn = base_card.get('data-entity-urn', '')
        job_id = urn.split(':')[-1] if urn else None

        # Job title (inside h3 tag with specific class)
        title_elem = card.find('h3', class_='base-search-card__title')
        title = title_elem.text.strip() if title_elem else None

        # Company name (inside h4 tag, which may contain an <a> to company page)
        company_elem = card.find('h4', class_='base-search-card__subtitle')
        company = company_elem.text.strip() if company_elem else None

        # Job link (anchor tag that leads to the job posting)
        link_elem = card.find('a', class_='base-card__full-link')
        job_link = link_elem['href'].strip() if link_elem else None
        if job_link and job_link.startswith('/'):
            job_link = "https://www.linkedin.com" + job_link  # convert relative link to absolute

        # Posted date (inside <time> tag). It might have 'datetime' attribute or just text.
        date_elem = card.find('time', class_='job-search-card__listdate') \
                   or card.find('time', class_='job-search-card__listdate--new')
        if date_elem:
            # Use the 'datetime' attribute if available, otherwise use text (e.g., "3 days ago")
            posted_date = date_elem.get('datetime', date_elem.text).strip()
        else:
            posted_date = None

        # Fetch job description using the job ID (to filter by keywords)
        description_text = ""
        if job_id:
            detail_url = f"https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{job_id}"
            try:
                detail_resp = session.get(detail_url, timeout=10)
            except requests.RequestException as e:
                print(f"Error fetching details for job {job_id}: {e}")
                continue  # skip this job if details can't be fetched
            if detail_resp.status_code == 429:
                # Handle rate limit on detail fetch
                print(f"Rate limit hit on job ID {job_id}. Waiting 30 seconds...")
                time.sleep(30)
                try:
                    detail_resp = session.get(detail_url, timeout=10)
                except requests.RequestException:
                    continue  # if it fails again, skip
            if detail_resp.status_code == 200:
                detail_soup = BeautifulSoup(detail_resp.text, 'html.parser')
                # The job description is in a section of the page with 'description' in its class&#8203;:contentReference[oaicite:10]{index=10}
                desc_container = detail_soup.find(lambda tag: tag.name == "div" and tag.get_text() and 'description' in (tag.get('class') or []))
                # Fallback: find any element with 'description' in class name
                if not desc_container:
                    desc_container = detail_soup.find('div', {'class': lambda x: x and 'description' in x})
                if desc_container:
                    description_text = desc_container.get_text(separator=" ", strip=True)

        # Filter out jobs with forbidden terms in the description
        if description_text:
            desc_lower = description_text.lower()
            if any(term in desc_lower for term in ["clearance", "citizen", "sponsor", "visa"]):
                # Skip this job posting if any of the terms are found
                continue

        # If passed the filter, store the job info
        jobs_data.append({
            "Job Title": title,
            "Company": company,
            "Job Link": job_link,
            "Posting Date": posted_date
        })
    # Go to next page of results
    start += 25

# Save the results to a CSV file
output_file = "intern_jobs_US.csv"
try:
    with open(output_file, mode='w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=["Job Title", "Company", "Job Link", "Posting Date"])
        writer.writeheader()
        writer.writerows(jobs_data)
    print(f"Saved {len(jobs_data)} job postings to {output_file}")
except Exception as e:
    print(f"Error saving CSV: {e}")
