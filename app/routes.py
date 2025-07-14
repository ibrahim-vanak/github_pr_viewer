import os
import threading
import requests
from flask import Flask, render_template, request, jsonify
from datetime import datetime, timedelta, timezone

app = Flask(__name__)

# === Secure token and org config ===
GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN', 'your-token-here')  # Set this in shell or .env
ORG_NAME = 'OptivaInc'

# === Default repos to show initially ===
DEFAULT_REPOS = [
    "OBP-Product-App-CM-Portal-Backend",
    "OBP-Product-App-Suite",
    "Optiva-Product-App-Api-Gw",
    "OBP-Product-App-CM-Portal-UI",
    "OBP-Product-CM-Portal-RAF",
    "OBP-Product-App-CM-Portal-Uploader"
]

REPO_CACHE = []  # Global repo cache


def get_repositories():
    """Fetch and cache filtered repositories from GitHub."""
    global REPO_CACHE

    if REPO_CACHE:
        return REPO_CACHE  # Return from cache

    try:
        repos = []
        headers = {'Authorization': f'token {GITHUB_TOKEN}'}
        page = 1

        while True:
            url = f'https://api.github.com/orgs/{ORG_NAME}/repos?per_page=100&page={page}'
            resp = requests.get(url, headers=headers)
            if resp.status_code != 200:
                break
            page_data = resp.json()
            if not page_data:
                break
            repos.extend(page_data)
            page += 1

        # Filter repos by prefix
        REPO_CACHE = [
            {"value": repo["name"], "text": repo["name"]}
            for repo in repos
            if repo["name"].startswith(("OBP", "Optiva", "orms"))
        ]

    except Exception as e:
        print("Error while fetching repos:", e)

    return REPO_CACHE


@app.route('/all_repos')
def all_repos():
    """AJAX route to serve repos to TomSelect."""
    return jsonify(get_repositories())


@app.route('/', methods=['GET', 'POST'])
def index():
    """Main form logic: render PR data or show form."""
    error = None
    pr_data = []
    selected_repos = []
    branch = request.form.get('branch', 'main')
    days = int(request.form.get('days', 7))

    if request.method == 'POST':
        selected_repos = request.form.getlist('repo')
        since_dt = datetime.now(timezone.utc) - timedelta(days=days)
        headers = {'Authorization': f'token {GITHUB_TOKEN}'}
        branch_not_found = []

        for repo in selected_repos:
            url = f'https://api.github.com/repos/{ORG_NAME}/{repo}/pulls?state=closed&base={branch}&per_page=100'
            resp = requests.get(url, headers=headers)

            if resp.status_code == 404:
                branch_not_found.append(repo)
                continue

            if resp.status_code != 200:
                error = f"Failed to fetch PRs from {repo}."
                continue

            for pr in resp.json():
                merged_at = pr.get("merged_at")
                if merged_at:
                    merged_at_dt = datetime.strptime(merged_at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                    if merged_at_dt > since_dt:
                        pr_data.append({
                            "repo": repo,
                            "title": pr["title"],
                            "author": pr["user"]["login"],
                            "merged_at": merged_at_dt.strftime("%Y-%m-%d %H:%M"),
                            "url": pr["html_url"]
                        })

        if branch_not_found:
            error = f"The branch '{branch}' does not exist in: {', '.join(branch_not_found)}."

    return render_template(
        'index.html',
        repo_list=DEFAULT_REPOS,
        pr_data=pr_data,
        selected_repos=selected_repos,
        branch=branch,
        days=days,
        error=error
    )


# === Background refresher ===
def start_background_repo_refresh():
    def refresh():
        get_repositories()
        threading.Timer(600, refresh).start()  # refresh every 10 min

    refresh()


# === App Entry Point ===
if __name__ == "__main__":
    start_background_repo_refresh()
    app.run(host="0.0.0.0", port=5050, debug=True)
