import asyncio
import random
import time
from argparse import ArgumentParser
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from playground import playgrounds
from sport_api import FudanAPI, get_routes


RUN_WINDOWS = {28: ('06:45', '07:15'), 33: ('15:20', '16:45'), 38: ('20:00', '20:30')}


def within_run_window(route_id, duration, now=None):
    now = now or datetime.now(ZoneInfo('Asia/Shanghai'))
    now = now.astimezone(ZoneInfo('Asia/Shanghai'))
    if route_id not in RUN_WINDOWS:
        print(f'SKIP: route {route_id} has no configured time window')
        return False
    start, end = RUN_WINDOWS[route_id]
    start = datetime.combine(now.date(), datetime.strptime(start, '%H:%M').time(), now.tzinfo)
    end = datetime.combine(now.date(), datetime.strptime(end, '%H:%M').time(), now.tzinfo)
    allowed = now.weekday() < 5 and start <= now and now + timedelta(seconds=duration + 30) <= end
    if not allowed:
        print(f'SKIP: Beijing time {now.isoformat(timespec="seconds")}; '
              f'route {route_id} requires weekdays {start:%H:%M}-{end:%H:%M}, '
              f'with {duration:.0f}s plus 30s reserved before closing')
    return allowed


async def main():
    parser = ArgumentParser()
    parser.add_argument('-v', '--view', action='store_true', help="list available routes")
    parser.add_argument('-r', '--route', help="set route ID", type=int)
    parser.add_argument('-t', '--time', help="total time, in seconds", type=int)
    parser.add_argument('-d', '--distance', help="total distance, in meters", type=int)
    parser.add_argument('-q', '--delay', action='store_true', help="delay for random time")
    args = parser.parse_args()

    if args.view:
        routes = await get_routes()
        supported_routes = filter(lambda r: r.id in playgrounds, routes)
        for route in supported_routes:
            route.pretty_print()
        exit()

    if args.route:
        # set distance
        distance = 1200
        if args.distance:
            distance = args.distance
        distance += random.uniform(-5.0, 25.0)

        # set time
        total_time = 360
        if args.time:
            total_time = args.time
        total_time += random.uniform(-10.0, 10.0)

        # Reject delayed schedules before any school API request.
        if not within_run_window(args.route, total_time):
            return

        # get routes from server
        print(f'CHECK: route/list for route {args.route}')
        routes = await get_routes()
        print(f'CHECK: route/list returned {len(routes)} routes')
        for route in routes:
            if route.id == args.route:
                selected_route = route
                break
        else:
            raise ValueError(f'不存在id为{args.route}的route')

        # delay random time, used in GitHub Action deployment
        if args.delay:
            sleep_time = random.randint(0, 240)
            time.sleep(sleep_time)

        # Re-check after querying routes and waiting; reserve time to finish.
        if not within_run_window(args.route, total_time):
            return

        # prepare & start running
        automator = FudanAPI(selected_route)
        playground = playgrounds[args.route]
        current_distance = 0
        print(f'CHECK: run/start for route {args.route} at '
              f'{datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")}')
        await automator.start()
        print(f"START: {selected_route.name}")
        while current_distance < distance:
            current_distance += distance / total_time
            message, _ = await asyncio.gather(
                automator.update(playground.random_offset(current_distance)), asyncio.sleep(1))
            print(f"UPDATE: {message} ({current_distance}m / {distance}m)")
        finish_message = await automator.finish(playground.coordinate(distance))
        print(f"FINISHED: {finish_message}")

if __name__ == '__main__':
    asyncio.run(main())
