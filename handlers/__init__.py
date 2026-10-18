from handlers import admin, help, history, leaderboard, match, moves, hub, mitb, profile, rumble, start, tag

routers = [start.router, help.router, match.router, moves.router, profile.router,
           leaderboard.router, history.router, rumble.router, tag.router, mitb.router, hub.router, admin.router]
