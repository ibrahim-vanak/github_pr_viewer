import requests
import smtplib
import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# CONFIG
GITHUB_TOKEN = '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'
REPOS = [
    "OptivaInc/OBP-Product-App-CM-Portal-Backend",
    "OptivaInc/OBP-Product-App-Suite",
    "OptivaInc/Optiva-Product-App-Api-Gw",
    "OptivaInc/OBP-Product-App-CM-Portal-UI",
    "OptivaInc/OBP-Product-CM-Portal-RAF",
    "OptivaInc/OBP-Product-App-CM-Portal-Uploader"
]
DAYS = 60 
SMTP_SERVER = "172.16.20.11"
EMAIL_FROM = "ibrahim.vanak@optiva.com"
EMAIL_TO = "ibrahim.vanak@optiva.com"

# HEADERS
headers = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json"
}

def get_recent_main_commits(repo, since):
    url = f"https://api.github.com/repos/{repo}/commits"
    params = {"sha": "main", "since": since.isoformat()}
    commits = requests.get(url, headers=headers, params=params).json()
    return {commit["sha"][:7] for commit in commits if "sha" in commit}

def get_develop_branches(repo):
    url = f"https://api.github.com/repos/{repo}/branches"
    branches = []
    page = 1
    while True:
        response = requests.get(url, headers=headers, params={"per_page": 100, "page": page}).json()
        if not response:
            break
        branches += [b["name"] for b in response if b["name"].startswith("develop/")]
        page += 1
    return branches

def branch_has_main_commit(repo, branch, main_shas):
    url = f"https://api.github.com/repos/{repo}/commits"
    params = {"sha": branch, "per_page": 100}
    commits = requests.get(url, headers=headers, params=params).json()
    return any(commit["sha"][:7] in main_shas for commit in commits if "sha" in commit)

def generate_report():
    since = datetime.datetime.utcnow() - datetime.timedelta(days=DAYS)
    html = '<html><body><h2>Develop Branch Sync Report (Last 7 Days)</h2>'
    html += '<style>table {border-collapse: collapse;} td, th {border: 1px solid #ccc; padding: 6px 10px;} th {background: #f5f5f5;}</style>'
    for repo in REPOS:
        html += f"<h3>{repo}</h3><table><tr><th>Branch</th><th>Merged from main?</th></tr>"
        try:
            main_shas = get_recent_main_commits(repo, since)
            branches = get_develop_branches(repo)
            for branch in branches:
                status = "✅ Yes" if branch_has_main_commit(repo, branch, main_shas) else "❌ No"
                html += f"<tr><td>{branch}</td><td>{status}</td></tr>"
        except Exception as e:
            html += f"<tr><td colspan='2'>Error: {str(e)}</td></tr>"
        html += "</table>"
    html += "</body></html>"
    return html

def send_email(html_content):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Develop Branch Sync Report - Last 7 Days"
    msg["From"] = EMAIL_FROM
    msg["To"] = EMAIL_TO
    msg.attach(MIMEText(html_content, "html"))
    with smtplib.SMTP(SMTP_SERVER, 25) as server:
        server.sendmail(EMAIL_FROM, EMAIL_TO, msg.as_string())

if __name__ == "__main__":
    html_report = generate_report()
    send_email(html_report)

