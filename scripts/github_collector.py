#!/usr/bin/env python3
"""
GitHub data collector for year review.
Fetches PRs, reviews, and commits from GitHub repositories.
"""

import requests
import json
from datetime import datetime, timezone
from typing import Dict, List, Optional
import time


class GitHubCollector:
    def __init__(self, pat: str, year: int = 2025):
        self.pat = pat
        self.year = year
        self.base_url = "https://api.github.com"
        self.headers = {
            "Authorization": f"token {pat}",
            "Accept": "application/vnd.github.v3+json"
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        
    def _make_request(self, url: str, params: Optional[Dict] = None) -> List[Dict]:
        """Make paginated API request."""
        all_items = []
        page = 1
        per_page = 100
        
        while True:
            if params:
                params['page'] = page
                params['per_page'] = per_page
            else:
                params = {'page': page, 'per_page': per_page}
            
            response = self.session.get(url, params=params)
            
            # Handle rate limiting
            if response.status_code == 403:
                reset_time = int(response.headers.get('X-RateLimit-Reset', time.time() + 60))
                wait_time = max(0, reset_time - int(time.time()))
                if wait_time > 0:
                    print(f"Rate limited. Waiting {wait_time} seconds...")
                    time.sleep(wait_time + 1)
                    continue
            
            response.raise_for_status()
            data = response.json()
            
            # GitHub search API returns {'items': [...], 'total_count': ...}
            if isinstance(data, dict) and 'items' in data:
                items = data['items']
            else:
                items = data if isinstance(data, list) else []
            
            if not items:
                break
                
            all_items.extend(items)
            
            # Check if there are more pages
            if len(items) < per_page:
                break
                
            page += 1
            time.sleep(0.5)  # Be nice to the API
            
        return all_items
    
    def get_user_prs(self, username: str) -> List[Dict]:
        """Get all PRs authored by user in the year."""
        start_date = f"{self.year}-01-01T00:00:00Z"
        end_date = f"{self.year}-12-31T23:59:59Z"
        
        # Search API for PRs authored by user
        query = f"author:{username} type:pr created:{start_date}..{end_date}"
        url = f"{self.base_url}/search/issues"
        params = {"q": query, "sort": "created", "order": "asc"}
        
        print(f"Fetching PRs for {username}...")
        prs = self._make_request(url, params)
        
        # Get detailed PR info
        detailed_prs = []
        for pr in prs:
            pr_url = pr.get('pull_request', {}).get('url') or pr.get('url', '').replace('/issues/', '/pulls/')
            if '/pulls/' in pr_url:
                try:
                    pr_detail = self.session.get(pr_url).json()
                    detailed_prs.append({
                        'number': pr_detail.get('number'),
                        'title': pr_detail.get('title'),
                        'body': pr_detail.get('body', ''),
                        'state': pr_detail.get('state'),
                        'created_at': pr_detail.get('created_at'),
                        'merged_at': pr_detail.get('merged_at'),
                        'url': pr_detail.get('html_url'),
                        'repo': pr_detail.get('base', {}).get('repo', {}).get('full_name', ''),
                        'labels': [l.get('name') for l in pr_detail.get('labels', [])],
                        'commits': pr_detail.get('commits', 0),
                        'additions': pr_detail.get('additions', 0),
                        'deletions': pr_detail.get('deletions', 0)
                    })
                    time.sleep(0.1)
                except Exception as e:
                    print(f"Error fetching PR {pr.get('number')}: {e}")
                    continue
        
        return detailed_prs
    
    def get_user_reviews(self, username: str) -> List[Dict]:
        """Get all PRs reviewed by user in the year."""
        start_date = f"{self.year}-01-01T00:00:00Z"
        end_date = f"{self.year}-12-31T23:59:59Z"
        
        # Search API for PRs reviewed by user
        query = f"reviewed-by:{username} type:pr created:{start_date}..{end_date}"
        url = f"{self.base_url}/search/issues"
        params = {"q": query, "sort": "created", "order": "asc"}
        
        print(f"Fetching PR reviews for {username}...")
        prs = self._make_request(url, params)
        
        # Get review details
        reviewed_prs = []
        for pr in prs:
            pr_url = pr.get('pull_request', {}).get('url') or pr.get('url', '').replace('/issues/', '/pulls/')
            if '/pulls/' in pr_url:
                # Get reviews for this PR
                repo_match = pr_url.replace(f"{self.base_url}/repos/", "").split("/pulls/")
                if len(repo_match) == 2:
                    repo = repo_match[0]
                    pr_num = repo_match[1]
                    reviews_url = f"{self.base_url}/repos/{repo}/pulls/{pr_num}/reviews"
                    try:
                        reviews = self.session.get(reviews_url).json()
                        user_reviews = [r for r in reviews if r.get('user', {}).get('login') == username]
                        if user_reviews:
                            reviewed_prs.append({
                                'number': pr.get('number'),
                                'title': pr.get('title'),
                                'url': pr.get('html_url'),
                                'repo': repo,
                                'created_at': pr.get('created_at'),
                                'review_state': user_reviews[0].get('state'),
                                'reviewed_at': user_reviews[0].get('submitted_at')
                            })
                        time.sleep(0.1)
                    except Exception as e:
                        print(f"Error fetching reviews for PR {pr.get('number')}: {e}")
                        continue
        
        return reviewed_prs
    
    def get_repo_commits(self, repo: str, username: str) -> List[Dict]:
        """Get commits from a repository by user."""
        start_date = f"{self.year}-01-01T00:00:00Z"
        end_date = f"{self.year}-12-31T23:59:59Z"
        
        url = f"{self.base_url}/repos/{repo}/commits"
        params = {
            "author": username,
            "since": start_date,
            "until": end_date
        }
        
        print(f"Fetching commits from {repo} for {username}...")
        commits = self._make_request(url, params)
        
        return [{
            'sha': c.get('sha'),
            'message': c.get('commit', {}).get('message', ''),
            'date': c.get('commit', {}).get('author', {}).get('date'),
            'url': c.get('html_url'),
            'repo': repo
        } for c in commits]
    
    def collect_user_data(self, username: str, repos: List[str]) -> Dict:
        """Collect all GitHub data for a user."""
        if not username:
            return {
                'prs_authored': [],
                'prs_reviewed': [],
                'commits': []
            }
        
        data = {
            'prs_authored': self.get_user_prs(username),
            'prs_reviewed': self.get_user_reviews(username),
            'commits': []
        }
        
        # Get commits from specified repos
        for repo in repos:
            try:
                commits = self.get_repo_commits(repo, username)
                data['commits'].extend(commits)
            except Exception as e:
                print(f"Error fetching commits from {repo}: {e}")
                continue
        
        return data


if __name__ == "__main__":
    import sys
    from pathlib import Path
    
    # Load config
    config_path = Path(__file__).parent.parent / "config" / "team_config.json"
    with open(config_path) as f:
        config = json.load(f)
    
    collector = GitHubCollector(config['github_pat'], config['year'])
    
    # Test with first member
    if len(sys.argv) > 1:
        username = sys.argv[1]
        repos = config['repositories']
        data = collector.collect_user_data(username, repos)
        print(json.dumps(data, indent=2))
    else:
        print("Usage: python github_collector.py <github_username>")

