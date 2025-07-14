import os 
from flask import Flask, render_template, request, jsonify
import requests
from datetime import datetime, timedelta, timezone

app = Flask(__name__)

GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN') 
ORG_NAME = 'OptivaInc'

DEFAULT_REPOS = [
    "OBP-Product-App-CM-Portal-Backend",
    "OBP-Product-App-Suite",
    "Optiva-Product-App-Api-Gw",
    "OBP-Product-App-CM-Portal-UI",
    "OBP-Product-CM-Portal-RAF",
    "OBP-Product-App-CM-Portal-Uploader"
]

REPO_CACHE = []


def get_repositories():
    if REPO_CACHE:
        return REPO_CACHE

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

    filtered = [
        {"value": repo["name"], "text": repo["name"]}
        for repo in repos
        if repo["name"].startswith(("OBP", "Optiva"))
    ]
    REPO_CACHE.extend(filtered)
    return filtered


@app.route('/all_repos')
def all_repos():
    # Use the cached or freshly fetched repo list
    return jsonify(get_repositories())


@app.route('/', methods=['GET', 'POST'])
def index():
    error = None
    pr_data = []
    branch = request.form.get('branch', 'main')
    days = int(request.form.get('days', 7))
    selected_repos = request.form.getlist('repo') if request.method == 'POST' else DEFAULT_REPOS

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
        repo_list=get_repositories(),
        pr_data=pr_data,
        selected_repos=selected_repos,
        branch=branch,
        days=days,
        error=error
    )



if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5050, debug=True)
