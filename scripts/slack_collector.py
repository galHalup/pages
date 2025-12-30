#!/usr/bin/env python3
"""
Slack data collector for year review.
Fetches messages and activity from Slack.
"""

import requests
import json
from datetime import datetime, timezone
from typing import Dict, List, Optional
import time


class SlackCollector:
    def __init__(self, token: str, year: int = 2025):
        self.token = token
        self.year = year
        self.base_url = "https://slack.com/api"
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        
        # Get user ID from email
        self.user_cache = {}
        
    def _make_request(self, method: str, endpoint: str, params: Optional[Dict] = None) -> Dict:
        """Make API request to Slack."""
        url = f"{self.base_url}/{endpoint}"
        
        if method.upper() == "GET":
            response = self.session.get(url, params=params)
        else:
            response = self.session.post(url, json=params)
        
        response.raise_for_status()
        data = response.json()
        
        if not data.get('ok'):
            error = data.get('error', 'unknown')
            raise Exception(f"Slack API error: {error}")
        
        return data
    
    def get_user_id(self, email: str) -> Optional[str]:
        """Get Slack user ID from email."""
        if email in self.user_cache:
            return self.user_cache[email]
        
        # List all users and find by email
        data = self._make_request("GET", "users.list")
        users = data.get('members', [])
        
        for user in users:
            profile = user.get('profile', {})
            if profile.get('email') == email:
                user_id = user.get('id')
                self.user_cache[email] = user_id
                return user_id
        
        return None
    
    def get_user_messages(self, email: str) -> Dict:
        """Get messages sent by user."""
        user_id = self.get_user_id(email)
        if not user_id:
            print(f"User {email} not found in Slack")
            return {
                'total_messages': 0,
                'messages_by_month': {},
                'channels': {},
                'messages': []
            }
        
        print(f"Fetching Slack messages for {email} (user_id: {user_id})...")
        
        # Search for messages by user
        start_date = datetime(self.year, 1, 1, tzinfo=timezone.utc).timestamp()
        end_date = datetime(self.year, 12, 31, 23, 59, 59, tzinfo=timezone.utc).timestamp()
        
        # Use search.messages to find messages from user
        query = f"from:{user_id}"
        params = {
            "query": query,
            "count": 100,
            "sort": "timestamp"
        }
        
        all_messages = []
        cursor = None
        
        try:
            while True:
                if cursor:
                    params['cursor'] = cursor
                
                data = self._make_request("GET", "search.messages", params)
                matches = data.get('messages', {}).get('matches', [])
                
                if not matches:
                    break
                
                for match in matches:
                    ts = float(match.get('ts', 0))
                    if start_date <= ts <= end_date:
                        all_messages.append({
                            'text': match.get('text', ''),
                            'channel': match.get('channel', {}).get('name', 'unknown'),
                            'channel_id': match.get('channel', {}).get('id', ''),
                            'timestamp': ts,
                            'permalink': match.get('permalink', '')
                        })
                
                # Check pagination
                pagination = data.get('messages', {}).get('pagination', {})
                cursor = pagination.get('next_cursor')
                if not cursor:
                    break
                
                time.sleep(1)  # Rate limiting
                
        except Exception as e:
            print(f"Error searching messages: {e}")
            # Fallback: try to get messages from channels user is in
            return self._get_messages_from_channels(user_id, start_date, end_date)
        
        # Group by month
        messages_by_month = {}
        channels = {}
        
        for msg in all_messages:
            dt = datetime.fromtimestamp(msg['timestamp'], tz=timezone.utc)
            month_key = dt.strftime('%Y-%m')
            
            if month_key not in messages_by_month:
                messages_by_month[month_key] = 0
            messages_by_month[month_key] += 1
            
            channel = msg['channel']
            if channel not in channels:
                channels[channel] = 0
            channels[channel] += 1
        
        return {
            'total_messages': len(all_messages),
            'messages_by_month': messages_by_month,
            'channels': channels,
            'messages': all_messages[:1000]  # Limit to 1000 most recent
        }
    
    def _get_messages_from_channels(self, user_id: str, start_ts: float, end_ts: float) -> Dict:
        """Fallback: get messages from channels user is member of."""
        # Get list of channels
        channels_data = self._make_request("GET", "conversations.list", {"types": "public_channel,private_channel"})
        channels = channels_data.get('channels', [])
        
        all_messages = []
        messages_by_month = {}
        channels_dict = {}
        
        for channel in channels[:50]:  # Limit to 50 channels to avoid rate limits
            channel_id = channel.get('id')
            channel_name = channel.get('name')
            
            try:
                # Get messages from channel
                params = {
                    "channel": channel_id,
                    "oldest": str(start_ts),
                    "latest": str(end_ts),
                    "limit": 100
                }
                
                data = self._make_request("GET", "conversations.history", params)
                messages = data.get('messages', [])
                
                for msg in messages:
                    if msg.get('user') == user_id:
                        ts = float(msg.get('ts', 0))
                        dt = datetime.fromtimestamp(ts, tz=timezone.utc)
                        month_key = dt.strftime('%Y-%m')
                        
                        all_messages.append({
                            'text': msg.get('text', ''),
                            'channel': channel_name,
                            'channel_id': channel_id,
                            'timestamp': ts,
                            'permalink': ''
                        })
                        
                        if month_key not in messages_by_month:
                            messages_by_month[month_key] = 0
                        messages_by_month[month_key] += 1
                        
                        if channel_name not in channels_dict:
                            channels_dict[channel_name] = 0
                        channels_dict[channel_name] += 1
                
                time.sleep(0.5)
                
            except Exception as e:
                print(f"Error fetching messages from channel {channel_name}: {e}")
                continue
        
        return {
            'total_messages': len(all_messages),
            'messages_by_month': messages_by_month,
            'channels': channels_dict,
            'messages': all_messages
        }


if __name__ == "__main__":
    import sys
    from pathlib import Path
    
    # Load config
    config_path = Path(__file__).parent.parent / "config" / "team_config.json"
    with open(config_path) as f:
        config = json.load(f)
    
    collector = SlackCollector(config['slack_token'], config['year'])
    
    # Test with first member
    if len(sys.argv) > 1:
        email = sys.argv[1]
        data = collector.get_user_messages(email)
        print(json.dumps(data, indent=2))
    else:
        print("Usage: python slack_collector.py <slack_email>")

