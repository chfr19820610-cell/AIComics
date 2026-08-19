#!/usr/bin/env python3
"""YouTube Data API v3 upload script.

Called by aicomic.publish.youtube_publisher via subprocess.

Usage:
    python scripts/yt_upload.py \
        --video /path/to/video.mp4 \
        --title "Episode Title" \
        --description "Description" \
        --tags "tag1,tag2" \
        --privacy public \
        --client-secret /path/to/client_secret.json \
        --credentials /path/to/credentials.json

Requires: google-api-python-client, google-auth-oauthlib
    pip install google-api-python-client google-auth-oauthlib

Returns: video URL on stdout, errors on stderr.
"""
from __future__ import annotations

import argparse
import sys
import os


def main() -> int:
    parser = argparse.ArgumentParser(description="Upload video to YouTube via Data API v3")
    parser.add_argument("--video", required=True, help="Video file path")
    parser.add_argument("--title", required=True, help="Video title")
    parser.add_argument("--description", default="", help="Video description")
    parser.add_argument("--tags", default="", help="Comma-separated tags")
    parser.add_argument("--privacy", default="public", choices=["public", "unlisted", "private"])
    parser.add_argument("--client-secret", required=True, help="OAuth client_secret.json path")
    parser.add_argument("--credentials", default="credentials.json", help="Token storage path")
    args = parser.parse_args()

    try:
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
        import pickle
    except ImportError:
        print("ERROR: Install google-api-python-client google-auth-oauthlib", file=sys.stderr)
        print("  pip install google-api-python-client google-auth-oauthlib", file=sys.stderr)
        return 1

    # OAuth2 flow
    scopes = ["https://www.googleapis.com/auth/youtube.upload"]
    token_path = args.credentials

    creds = None
    if os.path.exists(token_path):
        with open(token_path, "rb") as f:
            creds = pickle.load(f)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(args.client_secret, scopes)
            creds = flow.run_local_server(port=0)  # headless: use run_console if available
        with open(token_path, "wb") as f:
            pickle.dump(creds, f)

    # Build YouTube API client
    youtube = build("youtube", "v3", credentials=creds)

    # Upload
    tags = [t.strip() for t in args.tags.split(",") if t.strip()] if args.tags else []
    request = youtube.videos().insert(
        part="snippet,status",
        body={
            "snippet": {
                "title": args.title,
                "description": args.description,
                "tags": tags,
                "categoryId": "24",  # Entertainment
            },
            "status": {
                "privacyStatus": args.privacy,
                "selfDeclaredMadeForKids": False,
            },
        },
        media_body=MediaFileUpload(args.video, chunksize=-1, resumable=True),
    )

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"Upload: {int(status.progress() * 100)}%", file=sys.stderr)

    video_id = response["id"]
    video_url = f"https://www.youtube.com/watch?v={video_id}"
    print(video_url)
    return 0


if __name__ == "__main__":
    sys.exit(main())
