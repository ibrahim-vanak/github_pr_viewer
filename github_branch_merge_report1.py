import os
import subprocess
import smtplib
from prettytable import PrettyTable
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

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

# ===== EMAIL CONFIGURATION =====
SMTP_SERVER = "172.16.20.11"
SMTP_PORT = 25
EMAIL_FROM = "ibrahim.vanak@optiva.com"
EMAIL_TO = "ibrahim.vanak@optiva.com"
EMAIL_SUBJECT = "GitHub Branch Sync Report"
# ================================

def ensure_repo_cloned(repo_name, repo_url):
    path = os.path.join(CLONE_DIR, repo_name)
    if not os.path.isdir(path):
        print(f"🔄 Cloning {repo_name} from {repo_url}...")
        subprocess.run(["git", "clone", repo_url, path], check=True)
    else:
        print(f"🔁 Updating existing repo: {repo_name}...")
        subprocess.run(["git", "reset", "--hard"], cwd=path, stdout=subprocess.DEVNULL)
        subprocess.run(["git", "clean", "-fd"], cwd=path, stdout=subprocess.DEVNULL)
        subprocess.run(["git", "checkout", MAIN_BRANCH], cwd=path, stdout=subprocess.DEVNULL)
        subprocess.run(["git", "pull", "origin", MAIN_BRANCH], cwd=path, stdout=subprocess.DEVNULL)

    subprocess.run(["git", "fetch", "origin", "+refs/heads/*:refs/remotes/origin/*"],
                   cwd=path, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return path

def get_develop_branches(repo_path):
    result = subprocess.run(["git", "branch", "-r"], cwd=repo_path, stdout=subprocess.PIPE, text=True)
    branches = []
    for line in result.stdout.strip().splitlines():
        line = line.strip()
        if line.startswith("origin/develop/") and not line.endswith("/HEAD"):
            branches.append(line.replace("origin/", ""))
    return branches

def get_patch_ids(repo_path, branch):
    subprocess.run(["git", "reset", "--hard"], cwd=repo_path, stdout=subprocess.DEVNULL)
    subprocess.run(["git", "clean", "-fd"], cwd=repo_path, stdout=subprocess.DEVNULL)
    subprocess.run(["git", "checkout", branch], cwd=repo_path, stdout=subprocess.DEVNULL)
    log = subprocess.run(["git", "log", "--pretty=format:%H"], cwd=repo_path, stdout=subprocess.PIPE, text=True)
    commits = log.stdout.strip().splitlines()
    patch_ids = set()
    for commit in commits:
        try:
            diff = subprocess.run(["git", "show", commit], cwd=repo_path, stdout=subprocess.PIPE)
            patch_id = subprocess.run(["git", "patch-id", "--stable"], input=diff.stdout,
                                      stdout=subprocess.PIPE).stdout.decode().split()[0]
            patch_ids.add(patch_id)
        except Exception:
            continue
    return patch_ids

def build_report():
    os.makedirs(CLONE_DIR, exist_ok=True)
    table = PrettyTable()
    table.field_names = ["Repository", "Branch", "Content Synced with main"]

    for full_name in REPOS:
        repo_name = full_name.split("/")[-1]
        repo_url = f"https://{GITHUB_TOKEN + '@' if GITHUB_TOKEN else ''}github.com/{full_name}.git"
        repo_path = ensure_repo_cloned(repo_name, repo_url)

        try:
            main_patch_ids = get_patch_ids(repo_path, MAIN_BRANCH)
            branches = get_develop_branches(repo_path)

            for branch in branches:
                patch_ids = get_patch_ids(repo_path, branch)
                synced = main_patch_ids.issubset(patch_ids)
                table.add_row([repo_name, branch, "✅ Yes" if synced else "❌ No"])
        except Exception as e:
            table.add_row([repo_name, "N/A", f"❌ Error: {e}"])

    return table

def send_email_report(pretty_table):
    html_table = pretty_table.get_html_string(attributes={"border": "1", "cellpadding": "6", "cellspacing": "0"})

    html_content = f"""
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; }}
            h2 {{ color: #2c3e50; }}
            table {{ border-collapse: collapse; width: 100%; }}
            th, td {{ border: 1px solid #ddd; padding: 8px; }}
            th {{ background-color: #2c3e50; color: white; }}
            tr:nth-child(even) {{ background-color: #f2f2f2; }}
        </style>
    </head>
    <body>
        <h2>GitHub Branch Sync Report</h2>
        {html_table}
    </body>
    </html>
    """

    msg = MIMEMultipart("alternative")
    msg["Subject"] = EMAIL_SUBJECT
    msg["From"] = EMAIL_FROM
    msg["To"] = EMAIL_TO

    part1 = MIMEText("Please open this email in HTML format to view the sync report.", "plain")
    part2 = MIMEText(html_content, "html")

    msg.attach(part1)
    msg.attach(part2)

    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
        server.sendmail(EMAIL_FROM, EMAIL_TO, msg.as_string())

    print("📧 Email sent to", EMAIL_TO)

if __name__ == "__main__":
    print("\n📋 Sync Report:\n")
    report = build_report()
    print(report)
    send_email_report(report)

