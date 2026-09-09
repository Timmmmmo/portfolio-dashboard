#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""通过 GitHub Contents API 提交单文件（无需git网络推送）。
token 来源：优先环境变量 GH_TOKEN，其次 Windows 凭据管理器(git credential fill)。
用法: python gh_upload.py <repo内相对路径> [提交说明]
"""
import base64, json, os, subprocess, sys, urllib.request

REPO = 'Timmmmmo/portfolio-dashboard'

def get_token():
    if os.environ.get('GH_TOKEN'):
        return os.environ['GH_TOKEN']
    out = subprocess.run(['git', 'credential', 'fill'],
                         input='protocol=https\nhost=github.com\n\n',
                         capture_output=True, text=True, encoding='utf-8')
    if out.returncode != 0:
        raise RuntimeError('git credential fill failed')
    for line in out.stdout.splitlines():
        if line.startswith('password='):
            return line.split('=', 1)[1]
    raise RuntimeError('no token in credential manager')

def api(method, path, payload=None, token=None):
    url = 'https://api.github.com' + path
    data = json.dumps(payload).encode('utf-8') if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header('Authorization', 'Bearer ' + token)
    req.add_header('Accept', 'application/vnd.github+json')
    req.add_header('Content-Type', 'application/json')
    req.add_header('User-Agent', 'dashboard-bot')
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            body = r.read()
            return r.status, json.loads(body) if body else {}
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', 'ignore')
        return e.code, {'_err': body[:500]}

def main():
    if len(sys.argv) < 2:
        print('usage: gh_upload.py <path> [msg]')
        return 1
    path = sys.argv[1].lstrip('/')
    msg = sys.argv[2] if len(sys.argv) > 2 else 'auto: update ' + path
    with open(path, 'rb') as f:
        content = base64.b64encode(f.read()).decode()

    token = get_token()
    ep = '/repos/%s/contents/%s' % (REPO, path)
    code, resp = api('GET', ep, token=token)
    sha = resp.get('sha') if code == 200 else None

    payload = {'message': msg, 'content': content}
    if sha:
        payload['sha'] = sha
    code, resp = api('PUT', ep, payload, token)
    if code in (200, 201):
        print('uploaded %s -> commit %s' % (path, resp.get('commit', {}).get('sha', '?')[:7]))
        return 0
    print('FAIL %s %s %s' % (code, path, resp.get('_err', resp)), file=sys.stderr)
    return 1

if __name__ == '__main__':
    sys.exit(main())
