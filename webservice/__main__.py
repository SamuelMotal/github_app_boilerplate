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

#testchange
router = routing.Router()
cache = cachetools.LRUCache(maxsize=500)

routes = web.RouteTableDef()

@routes.get("/", name="home")
async def handle_get(request):
    content="Hello world"
    with open('Index.html','r') as file:
        content = file.read()
    return web.Response(text=content,content_type='text/html')


@routes.get("/js/index.js", name="index.js")
async def handle_get(request):
    content="Hello world"
    with open('./js/index.js','r') as file:
        content = file.read()
    return web.Response(text=content,content_type='text/html')

@routes.get("/css/styles.css", name="styles.css")
async def handle_get(request):
    content="Hello world"
    with open('./css/styles.css','r') as file:
        content = file.read()
    return web.Response(text=content,content_type='text/html')


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


@router.register("installation", action="created")
async def repo_installation_added(event, gh, *args, **kwargs):
    installation_id = event.data["installation"]["id"]
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
    app = web.Application()
    
    app.router.add_routes(routes)
    port = os.environ.get("PORT")
    if port is not None:
        port = int(port)
    print('starting db')
    connectDB()
    print('starting the server')
    web.run_app(app, port=port)
