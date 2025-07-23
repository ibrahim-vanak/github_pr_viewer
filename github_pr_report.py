#!/usr/bin/python

import os
import requests
import smtplib
import argparse
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

load_dotenv(dotenv_path='/opt/github-pr-viewer/.env')

GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
HEADERS = {
    "Accept": "application/vnd.github+json",
    "Authorization": f"Bearer {GITHUB_TOKEN}" if GITHUB_TOKEN else ""
}

# GitHub repositories to track
REPOSITORIES = [
    "OptivaInc/OBP-Product-App-CM-Portal-Backend",
    "OptivaInc/OBP-Product-App-Suite",
    "OptivaInc/Optiva-Product-App-Api-Gw",
    "OptivaInc/OBP-Product-App-CM-Portal-UI",
    "OptivaInc/OBP-Product-CM-Portal-RAF",
    "OptivaInc/OBP-Product-App-CM-Portal-Uploader"

]

user_name_cache = {}

def get_real_name(username, headers):
    if username in user_name_cache:
        return user_name_cache[username]

    user_url = f"https://api.github.com/users/{username}"
    response = requests.get(user_url, headers=headers)

    if response.status_code == 200:
        data = response.json()
        name = data.get("name") or username
        user_name_cache[username] = name
        return name
    else:
        return username


# Fetch merged PRs for a given repo and time window
def fetch_merged_prs(repo, branch='main', days_back=7):
    since_time = datetime.utcnow() - timedelta(days=int(days_back))
    url = f"https://api.github.com/repos/{repo}/pulls"
    params = {"state": "closed", "base": branch, "per_page": 100}
    results = []
    page = 1

    while True:
        response = requests.get(url, headers=HEADERS, params={**params, "page": page})
        if response.status_code != 200:
            return f"Error: {response.status_code} - {response.text}", []
        prs = response.json()
        if not prs:
            break
        for pr in prs:
            if pr.get("merged_at"):
                merged_at = datetime.strptime(pr["merged_at"], "%Y-%m-%dT%H:%M:%SZ")
                if merged_at >= since_time:
                    results.append({
                        "repo": repo,
                        "url": pr["html_url"],
                        "author": get_real_name(pr['user']['login'], headers),
                        "title": pr["title"],
                        "merged_at": merged_at.strftime("%Y-%m-%d %H:%M UTC")
                    })
        page += 1
    return None, results

# Build HTML with consistent column widths
def build_html_table_grouped(prs_by_repo, branch, days_back):
    start_date = (datetime.utcnow() - timedelta(days=int(days_back))).strftime("%Y-%m-%d")
    end_date = datetime.utcnow().strftime("%Y-%m-%d")

    html = "<p>Hello Team,</p>\n"
    html += (
        f"<p>Please find below the list of GitHub PRs merged to the "
        f"<span style='color: red;'>'{branch}'</span> branch in the last "
        f"<span style='color: red;'>{days_back}</span> day(s) "
        f"<b>({start_date} → {end_date})</b>:</p>\n"
    )

    for repo in REPOSITORIES:
        html += f"<h3 style='color: #d9534f;'>Repository: {repo}</h3>"
        prs = prs_by_repo.get(repo, [])
        if not prs:
            html += "<p><i>No PRs merged during this period.</i></p>\n"
            continue

        html += """
        <table border="1" cellpadding="6" cellspacing="0" style="border-collapse: collapse; width: 100%;">
            <tr style="background-color: #f2f2f2;">
                <th style="width: 20%;">Date</th>
                <th style="width: 45%;">PR Title</th>
                <th style="width: 20%;">Author</th>
                <th style="width: 15%;">PR Link</th>
            </tr>
        """
        for i, pr in enumerate(prs):
            bg_color = "#ffffff" if i % 2 == 0 else "#f9f9f9"
            html += f"""
            <tr style="background-color: {bg_color};">
                <td style="width: 20%;">{pr['merged_at']}</td>
                <td style="width: 45%;">{pr['title']}</td>
                <td style="width: 20%;">{pr['author']}</td>
                <td style="width: 15%;"><a href="{pr['url']}">View PR</a></td>
            </tr>
            """
        html += "</table><br/>"

    html += "<p>Regards,<br/>GitHub PR Notifier</p>"
    return html

# Send email via anonymous SMTP
def send_email_report(subject, html_content, from_email, to_email, smtp_server='localhost', smtp_port=25):
    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = from_email
    msg['To'] = ", ".join(to_email) if isinstance(to_email, list) else to_email

    html_part = MIMEText(html_content, 'html')
    msg.attach(html_part)

    try:
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.sendmail(from_email, to_email if isinstance(to_email, list) else [to_email], msg.as_string())
        print("✅ Email sent successfully.")
    except Exception as e:
        print(f"❌ Failed to send email: {e}")

# Main execution
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="GitHub PR Reporter")
    parser.add_argument("--branch", default="main", help="Branch name to check PRs against (default: main)")
    parser.add_argument("--days", type=int, default=7, help="Number of days to look back (default: 7)")
    args = parser.parse_args()

    branch = args.branch
    days_back = args.days

    prs_by_repo = {}
    for repo in REPOSITORIES:
        error, prs = fetch_merged_prs(repo, branch=branch, days_back=days_back)
        if error:
            print(f"[{repo}] Error: {error}")
        prs_by_repo[repo] = prs

    html_content = build_html_table_grouped(prs_by_repo, branch, days_back)
    send_email_report(
        subject=f"GitHub PR Merge Report to '{branch}' branch for Last {days_back} day(s)",
        html_content=html_content,
        from_email="ibrahim.vanak@optiva.com",
        to_email=["ibrahim.vanak@optiva.com", "obp-leads@optiva.com", "bronagh.dowey@optiva.com" "richard.mclaughlin@optiva.com", "malcolm.tye@optiva.com"],
        smtp_server="172.16.20.11",
        smtp_port=25
    )

