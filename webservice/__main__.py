import asyncio
import os
import sys
import traceback


import aiohttp
from aiohttp import web
import cachetools
from gidgethub import aiohttp as gh_aiohttp
from gidgethub import routing
from gidgethub import sansio
from gidgethub import apps
import os
import psycopg2
from cryptography.hazmat.backends import default_backend
import jwt
import time
import requests
import aiohttp_cors

router = routing.Router()
cache = cachetools.LRUCache(maxsize=500)
routes = web.RouteTableDef()


@routes.get("/", name="home")
async def handle_get(request):
    content = "Welcome"
    return web.Response(text=content,content_type='text/html')


@routes.get('/validate/{user}/{repository}')
def create(request):
    user=request.match_info['user']
    repository=request.match_info['repository']
    content = validateInstallation(user,repository)
    res = {"result": content}
    return web.json_response(res)


@routes.post("/webhook")
async def webhook(request):
    try:
        body = await request.read()
        secret = os.environ.get("GH_SECRET")
        event = sansio.Event.from_http(request.headers, body, secret=secret)
        if event.event == "ping":
            return web.Response(status=200)
        async with aiohttp.ClientSession() as session:
            gh = gh_aiohttp.GitHubAPI(session, "demo", cache=cache)

            await asyncio.sleep(1)
            await router.dispatch(event, gh)
        try:
            print("GH requests remaining:", gh.rate_limit.remaining)
        except AttributeError:
            pass
        return web.Response(status=200)
    except Exception as exc:
        traceback.print_exc(file=sys.stderr)
        return web.Response(status=500)


def validateInstallation(username,repository_name):
    private_key=os.environ.get("GH_PRIVATE_KEY")
    cert_bytes = private_key.encode()
    private_key = default_backend().load_pem_private_key(cert_bytes, None)

    time_since_epoch_in_seconds = int(time.time())
    
    payload = {
      # issued at time
      'iat': time_since_epoch_in_seconds,
      # JWT expiration time (10 minute maximum)
      'exp': time_since_epoch_in_seconds + (10 * 60),
      # GitHub App's identifier
      'iss': os.environ.get("GH_APP_ID")
    }

    actual_jwt = jwt.encode(payload, private_key, algorithm='RS256')

    #headers = {"Authorization": "Bearer {}".format(actual_jwt.decode())
    headersToSend = {"Authorization": "Bearer {}".format(actual_jwt.decode('utf-8')),"Accept": "application/vnd.github.machine-man-preview+json"}
    #resp = requests.get('https://api.github.com/users/user/installation', headers=headersToSend)
    #print('Code: ', resp.status_code)
    #print('Content: ', resp.content.decode())
    #print('Getting repository information...')
    #resp = requests.get('https://api.github.com/repos/SamuelMotal/didactic-guacamole/installation', headers=headersToSend)
    #print('Code: ', resp.status_code)
    #print('Content: ', resp.content.decode())
    #print('Getting another repository information...')
    #resp = requests.get('https://api.github.com/repos/SamuelMotal/github_app_boilerplate/installation', headers=headersToSend)
    #print('Code: ', resp.status_code)
    #print('Content: ', resp.content.decode())
    #https://docs.github.com/en/rest/reference/apps#get-a-repository-installation-for-the-authenticated-app
    resp = requests.get(f'https://api.github.com/repos/{username}/{repository_name}/installation', headers=headersToSend)
    print(resp.json())
    if(resp.status_code == 200 and resp.json()["account"]["login"]==username):
        return "installation validated!!"
    else:
        return "installation not validated!!!"


@router.register("installation", action="created")
async def repo_installation_added(event, gh, *args, **kwargs):
    installation_id = event.data["installation"]["id"]
    print("id:"+str(installation_id))
    installation_access_token = await apps.get_installation_access_token(
        gh,
        installation_id=installation_id,
        app_id=os.environ.get("GH_APP_ID"),
        private_key=os.environ.get("GH_PRIVATE_KEY"),
    )
    sender_name = event.data["sender"]["login"]

    for repo in event.data["repositories"]:

        repo_full_name = repo["full_name"]
        response = await gh.post(
            f"/repos/{repo_full_name}/issues",
            data={
                "title": "Thanks for installing me",
                "body": f"You're the best! @{sender_name}",
            },
            oauth_token=installation_access_token["token"],
        )
        issue_url = response["url"]
        await gh.patch(
            issue_url,
            data={"state": "closed"},
            oauth_token=installation_access_token["token"],
        )
        base64content="TWFuIGlzIGRpc3Rpbmd1aXNoZWQsIG5vdCBvbmx5IGJ5IGhpcyByZWFzb24sIGJ1dCBieSB0aGlzIHNpbmd1bGFyIHBhc3Npb24gZnJvbSBvdGhlciBhbmltYWxzLCB3aGljaCBpcyBhIGx1c3Qgb2YgdGhlIG1pbmQsIHRoYXQgYnkgYSBwZXJzZXZlcmFuY2Ugb2YgZGVsaWdodCBpbiB0aGUgY29udGludWVkIGFuZCBpbmRlZmF0aWdhYmxlIGdlbmVyYXRpb24gb2Yga25vd2xlZGdlLCBleGNlZWRzIHRoZSBzaG9ydCB2ZWhlbWVuY2Ugb2YgYW55IGNhcm5hbCBwbGVhc3VyZS4="
        response = await gh.post(
            f"/repos/SamuelMotal/didactic-guacamole/contents/sample.txt",
            data={
                "message": "Installing my action",
                "content": "testcontent",
            },
            oauth_token=installation_access_token["token"],
        ) 


@router.register("issue_comment", action="created")
async def issue_comment_created(event, gh, *args, **kwargs):
    username = event.data["sender"]["login"]
    installation_id = event.data["installation"]["id"]

    installation_access_token = await apps.get_installation_access_token(
        gh,
        installation_id=installation_id,
        app_id=os.environ.get("GH_APP_ID"),
        private_key=os.environ.get("GH_PRIVATE_KEY"),
    )
    comments_url = event.data["comment"]["url"]
    response = await gh.post(
        f"{comments_url}/reactions",
        data={"content": "heart"},
        oauth_token=installation_access_token["token"],
        accept="application/vnd.github.squirrel-girl-preview+json",
    )
    

    
def connectDB():
    #TODO CONNECT; CREATE TABLE; INSERT; READ SHOULD BE PROPERLY PROGRAMMED
    #DATABASE_URL = os.environ['DATABASE_URL']
    #conn = psycopg2.connect(DATABASE_URL, sslmode='require')
    pass
    
if __name__ == "__main__":  # pragma: no cover
    #test
    app = web.Application()
    app.router.add_routes(routes)
    cors = aiohttp_cors.setup(app)

    resource = cors.add(app.router.add_resource("/validate"))
    route = cors.add(
    resource.add_route("GET", create), {
        "http://client.example.org": aiohttp_cors.ResourceOptions(
            allow_credentials=True,
            expose_headers=("X-Custom-Server-Header",),
            allow_headers=("X-Requested-With", "Content-Type"),
            max_age=3600,
        )
    })
    port = os.environ.get("PORT")
    if port is not None:
        port = int(port)
    print('starting db')
    connectDB()
    print('starting the server')
    web.run_app(app, port=port)
