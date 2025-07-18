import os
import requests
from datetime import datetime, timedelta, timezone
from urllib.parse import quote, unquote
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from dotenv import load_dotenv

load_dotenv(dotenv_path='/opt/github-pr-viewer/.env')

GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
JENKINS_URL = "https://prime.labs.optiva.com"

# GitHub configuration
GITHUB_REPO = "OptivaInc/OBP-Product-App-Suite"
GITHUB_API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/tags"

# Email configuration
SMTP_SERVER = "172.16.20.11"
SMTP_PORT = 25
EMAIL_SENDER = "ibrahim.vanak@optiva.com"
EMAIL_RECIPIENTS = ["ibrahim.vanak@optiva.com"]
EMAIL_SUBJECT = "Jenkins Build Report - Last 30 Days"

# Per-repo config
REPO_CONFIG = {
    "OBP-Product-App-Suite": {
        "branches": "dynamic",
        "jenkins_path": "/job/obp/job/product/job/app"
    },
    "OBP-Product-App-CM-Portal-Backend": {
        "branches": ["main", "release/*"],
        "jenkins_path": "/job/obp/job/product/job/app"
    },
    "OBP-Product-App-CM-Portal-UI": {
        "branches": ["main", "release/*"],
        "jenkins_path": "/job/obp/job/product/job/app"
    },
    "Optiva-Product-App-Api-Gw": {
        "branches": ["main", "release/*"],
        "jenkins_path": "/job/optiva/job/product/job/app"
    },
    "OBP-Product-CM-Portal-RAF": {
        "branches": ["main", "release/*"],
        "jenkins_path": "/job/obp/job/product/job/app"
    },
    "OBP-Product-App-CM-Portal-Uploader": {
        "branches": ["main", "release/*"],
        "jenkins_path": "/job/obp/job/product/job/app"
    },
    "OBP-Product-RTS-Apigw": {
        "branches": ["develop", "release/*"],
        "jenkins_path": "/job/obp/job/product/job/rts"
    }
}

# Jenkins credentials
USERNAME = os.environ.get("JENKINS_USER")
API_TOKEN = os.environ.get("JENKINS_API_TOKEN")
AUTH = (USERNAME, API_TOKEN) if USERNAME and API_TOKEN else None

# Time window
DAYS = 30
now = datetime.now(timezone.utc)
cutoff = now - timedelta(days=DAYS)

def fetch_recent_builds(repo, branch, path):
    encoded_branch = quote(branch, safe='')
    url = f"{JENKINS_URL}{path}/job/{repo}/job/{encoded_branch}/api/json?tree=builds[number,url,timestamp,result,id,duration]"
    try:
        resp = requests.get(url, auth=AUTH, timeout=10)
        if resp.status_code != 200:
            return []
        builds = resp.json().get("builds", [])
        return [
            {
                "number": b["number"],
                "result": b.get("result", "UNKNOWN"),
                "url": b["url"],
                "time": datetime.fromtimestamp(b["timestamp"] / 1000, tz=timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
            }
            for b in builds
            if datetime.fromtimestamp(b["timestamp"] / 1000, tz=timezone.utc) >= cutoff
        ]
    except:
        return []

def discover_release_branches(repo, path):
    url = f"{JENKINS_URL}{path}/job/{repo}/api/json?tree=jobs[name,url]"
    try:
        resp = requests.get(url, auth=AUTH, timeout=10)
        jobs = resp.json().get("jobs", [])
        return [job["name"] for job in jobs if unquote(job["name"]).startswith("release/")]
    except:
        return []

def discover_github_tags():
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    valid_tags = []
    try:
        resp = requests.get(GITHUB_API_URL, headers=headers, timeout=10)
        tags = resp.json()
        for tag in tags:
            name = tag["name"]
            if name.startswith(("v1", "v2")):
                commit_url = tag["commit"]["url"]
                commit_resp = requests.get(commit_url, headers=headers, timeout=10)
                date_str = commit_resp.json()["commit"]["committer"]["date"]
                commit_date = datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                if commit_date >= cutoff:
                    valid_tags.append(name)
        return valid_tags
    except:
        return []

def generate_html_report(all_results):
    html = f"""<html><head><style>
        table {{ width: 100%; border-collapse: collapse; font-family: Arial; }}
        th, td {{ border: 1px solid #ccc; padding: 6px; font-size: 14px; }}
        th {{ background: #f2f2f2; }}
        .repo-link {{ font-size: 16px; font-weight: bold; color: #1a0dab; }}
        .branch-section {{ background-color: #f9f9f9; }}
        .status-SUCCESS {{ color: green; font-weight: bold; }}
        .status-FAILURE {{ color: red; font-weight: bold; }}
        .status-ABORTED {{ color: gray; }}
        .status-UNSTABLE {{ color: orange; }}
    </style></head><body>
    <h2>Jenkins Build Report (Last {DAYS} Days)</h2>"""

    grouped = {}
    for (repo, branch), builds in all_results.items():
        decoded = unquote(branch)
        for b in builds:
            b["datetime"] = datetime.strptime(b["time"], "%Y-%m-%d %H:%M:%S")
        grouped.setdefault(repo, {}).setdefault(decoded, []).extend(builds)

    repos_with_data = set(grouped.keys())
    all_repos = set(REPO_CONFIG.keys())
    no_data_repos = all_repos - repos_with_data

    for repo, branches in grouped.items():
        jenkins_url = f"{JENKINS_URL}{REPO_CONFIG[repo]['jenkins_path']}/job/{repo}/"
        html += f"<h3><a class='repo-link' href='{jenkins_url}'>{repo} 🔗</a></h3>"
        html += "<table><tr><th>Branch/Tag</th><th>Build #</th><th>Status</th><th>Time</th><th>Link</th></tr>"

        for i, branch in enumerate(sorted(branches)):
            builds = sorted(branches[branch], key=lambda b: b["datetime"], reverse=True)
            html += f"<tr class='branch-section'><td rowspan='{len(builds)}'>{branch}</td>"
            for j, b in enumerate(builds):
                if j > 0:
                    html += "<tr>"
                html += f"<td>{b['number']}</td><td class='status-{b['result']}'>{b['result']}</td><td>{b['time']}</td><td><a href='{b['url']}'>Link</a></td></tr>"
        html += "</table><br/>"

    for repo in sorted(no_data_repos):
        jenkins_url = f"{JENKINS_URL}{REPO_CONFIG[repo]['jenkins_path']}/job/{repo}/"
        html += f"<h3><a class='repo-link' href='{jenkins_url}'>{repo} 🔗</a></h3>"
        html += f"<p style='color:gray;'>⚠️ No builds in the last {DAYS} days on the specified branches.</p>"

    html += "</body></html>"
    return html

def send_email(html_content):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = EMAIL_SUBJECT
    msg["From"] = EMAIL_SENDER
    msg["To"] = ", ".join(EMAIL_RECIPIENTS)
    msg.attach(MIMEText(html_content, "html"))
    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
        server.sendmail(EMAIL_SENDER, EMAIL_RECIPIENTS, msg.as_string())

def main():
    all_results = {}
    for repo, config in REPO_CONFIG.items():
        branches = config["branches"]
        path = config["jenkins_path"]
        final_branches = []

        if branches == "dynamic":
            final_branches = discover_release_branches(repo, path) + discover_github_tags()
        else:
            for branch in branches:
                if branch == "release/*":
                    final_branches.extend(discover_release_branches(repo, path))
                else:
                    final_branches.append(branch)

        for branch in final_branches:
            builds = fetch_recent_builds(repo, branch, path)
            if builds:
                all_results[(repo, branch)] = builds
                print(f"\n✅ Builds for {repo} -- {unquote(branch)} (last {DAYS} days):")
                for b in builds:
                    print(f"  - #{b['number']} | {b['result']} | {b['time']} | {b['url']}")

    if all_results:
        html_report = generate_html_report(all_results)
        send_email(html_report)
        print("\n📧 Email report sent.")
    else:
        print("\n⚠️ No recent builds found. No email sent.")

if __name__ == "__main__":
    main()
