import os
from flask import Flask, render_template, request, jsonify, redirect, url_for, session
import requests
from datetime import datetime, timedelta, timezone

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'dummy_secret')  # Required for session support

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
    return jsonify(get_repositories())


@app.route('/', methods=['GET', 'POST'])
def index():
    error = None
    pr_data = []
    repo_statuses = {}

    if request.method == 'POST':
        selected = request.form.getlist('repo')
        # Special handling for "Default Repos" token
        if '__default__' in selected:
            session['selected_repos'] = DEFAULT_REPOS
        else:
            session['selected_repos'] = selected

        session['branch'] = request.form.get('branch', 'main')
        session['days'] = request.form.get('days', '7')
        return redirect(url_for('index'))

    # Load from session or fallback
    selected_repos = session.pop('selected_repos', DEFAULT_REPOS)
    branch = session.pop('branch', 'main')
    days = int(session.pop('days', 7))

    since_dt = datetime.now(timezone.utc) - timedelta(days=days)
    headers = {'Authorization': f'token {GITHUB_TOKEN}'}

    for repo in selected_repos:
        branch_trimmed = branch.strip()
        branch_check_url = f'https://api.github.com/repos/{ORG_NAME}/{repo}/branches/{branch_trimmed}'
        branch_resp = requests.get(branch_check_url, headers=headers)

        if branch_resp.status_code == 404:
            repo_statuses[repo] = f"⚠️ Branch '{branch_trimmed}' not found in {repo}"
            continue
        elif branch_resp.status_code != 200:
            repo_statuses[repo] = f"❌ Error checking branch '{branch_trimmed}' in {repo} (HTTP {branch_resp.status_code})"
            continue

        # Proceed only if branch exists
        url = f'https://api.github.com/repos/{ORG_NAME}/{repo}/pulls?state=closed&base={branch_trimmed}&per_page=100'
        resp = requests.get(url, headers=headers)
        if resp.status_code != 200:
            repo_statuses[repo] = f"❌ Failed to fetch PRs from {repo} (HTTP {resp.status_code})"
            continue

        merged_prs = []
        for pr in resp.json():
            merged_at = pr.get("merged_at")
            if merged_at:
                merged_at_dt = datetime.strptime(merged_at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                if merged_at_dt > since_dt:
                    merged_prs.append({
                        "repo": repo,
                        "title": pr["title"],
                        "author": pr["user"]["login"],
                        "merged_at": merged_at_dt.strftime("%Y-%m-%d %H:%M"),
                        "url": pr["html_url"]
                    })

        if merged_prs:
            pr_data.extend(merged_prs)
        else:
            # Explicitly check if status was already set before
            if repo not in repo_statuses:
                repo_statuses[repo] = f"ℹ️ No PRs merged into '{branch_trimmed}' in the last {days} days."

    return render_template(
        'index.html',
        repo_list=DEFAULT_REPOS,
        pr_data=pr_data,
        repo_statuses=repo_statuses,
        selected_repos=selected_repos,
        branch=branch,
        days=days,
        error=error
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5050, debug=True)
