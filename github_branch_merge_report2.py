import os
import subprocess
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# ===== CONFIGURATION =====
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
REPOS = [
    "OptivaInc/OBP-Product-App-CM-Portal-Backend",
    "OptivaInc/OBP-Product-App-Suite",
    "OptivaInc/Optiva-Product-App-Api-Gw",
    "OptivaInc/OBP-Product-App-CM-Portal-UI",
    "OptivaInc/OBP-Product-CM-Portal-RAF",
    "OptivaInc/OBP-Product-App-CM-Portal-Uploader"
]
CLONE_DIR = "./repos"
MAIN_BRANCH = "main"

# Email config
SMTP_SERVER = "172.16.20.11"
SMTP_PORT = 25
EMAIL_FROM = "ibrahim.vanak@optiva.com"
EMAIL_TO = "ibrahim.vanak@optiva.com"
EMAIL_SUBJECT = "GitHub Branch Sync Report"
# ==========================

def ensure_repo_cloned(repo_name, repo_url):
    path = os.path.join(CLONE_DIR, repo_name)
    if not os.path.isdir(path):
        print(f"🔄 Cloning {repo_name}...")
        subprocess.run(["git", "clone", repo_url, path], check=True)
    else:
        print(f"🔁 Updating {repo_name}...")
        subprocess.run(["git", "reset", "--hard"], cwd=path)
        subprocess.run(["git", "clean", "-fd"], cwd=path)
        subprocess.run(["git", "checkout", MAIN_BRANCH], cwd=path)
        subprocess.run(["git", "pull"], cwd=path)
    
    subprocess.run(
        ["git", "fetch", "origin", "+refs/heads/*:refs/remotes/origin/*"],
        cwd=path,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    return path

def get_develop_branches(repo_path):
    result = subprocess.run(["git", "branch", "-r"], cwd=repo_path, stdout=subprocess.PIPE, text=True)
    branches = []
    for line in result.stdout.strip().splitlines():
        line = line.strip()
        if line.startswith("origin/develop") and not line.endswith("/HEAD"):
            branches.append(line.replace("origin/", ""))
    return branches

def get_patch_ids(repo_path, branch):
    subprocess.run(["git", "checkout", branch], cwd=repo_path, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    log = subprocess.run(
        ["git", "log", "--pretty=format:%H"],
        cwd=repo_path,
        stdout=subprocess.PIPE,
        text=True
    ).stdout.strip().splitlines()

    patch_ids = set()
    for commit in log:
        try:
            diff = subprocess.run(["git", "show", commit], cwd=repo_path, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            patch_id = subprocess.run(["git", "patch-id", "--stable"],
                                      input=diff.stdout,
                                      stdout=subprocess.PIPE,
                                      stderr=subprocess.DEVNULL).stdout.decode().split()[0]
            patch_ids.add(patch_id)
        except Exception:
            continue
    return patch_ids

def build_report_data():
    os.makedirs(CLONE_DIR, exist_ok=True)
    report_data = {}

    for full_name in REPOS:
        repo_name = full_name.split("/")[-1]
        repo_url = f"https://{GITHUB_TOKEN + '@' if GITHUB_TOKEN else ''}github.com/{full_name}.git"
        repo_path = ensure_repo_cloned(repo_name, repo_url)
        report_data[repo_name] = []

        try:
            main_patch_ids = get_patch_ids(repo_path, MAIN_BRANCH)
            branches = get_develop_branches(repo_path)

            for branch in branches:
                patch_ids = get_patch_ids(repo_path, branch)
                synced = main_patch_ids.issubset(patch_ids)
                report_data[repo_name].append((branch, "✅ Yes" if synced else "❌ No"))
        except Exception as e:
            report_data[repo_name].append(("N/A", f"❌ Error: {e}"))

    return report_data

def build_html_report(report_data):
    style = """
    <style>
    body { font-family: Arial, sans-serif; }
    table { border-collapse: collapse; margin-top: 10px; width: 100%; }
    th, td { border: 1px solid #ccc; padding: 8px; text-align: left; }
    th { background-color: #f2f2f2; }
    h2 { margin-top: 30px; }
    </style>
    """
    html = f"<html><head>{style}</head><body><h1>GitHub Branch Sync Report</h1>"

    for repo, rows in report_data.items():
        html += f"<h2>📦 {repo}</h2>"
        html += "<table><tr><th>Branch</th><th>Content Synced with main</th></tr>"
        for branch, status in rows:
            html += f"<tr><td>{branch}</td><td>{status}</td></tr>"
        html += "</table>"

    html += "</body></html>"
    return html

def send_email_report(html_content):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = EMAIL_SUBJECT
    msg["From"] = EMAIL_FROM
    msg["To"] = EMAIL_TO

    html_part = MIMEText(html_content, "html")
    msg.attach(html_part)

    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
        server.sendmail(EMAIL_FROM, EMAIL_TO, msg.as_string())

if __name__ == "__main__":
    print("\n🔍 Building GitHub branch sync report...\n")
    report_data = build_report_data()
    html_report = build_html_report(report_data)
    send_email_report(html_report)
    print("📬 Report emailed successfully.")

