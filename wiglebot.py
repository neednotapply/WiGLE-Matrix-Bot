import nio
import aiohttp
import asyncio
import json
import logging
import inflect
import time
from datetime import datetime
import os

logging.basicConfig(level=logging.INFO)

def load_config():
    try:
        with open("config.json", "r") as config_file:
            return json.load(config_file)
    except FileNotFoundError:
        logging.critical("The config.json file was not found.")
        raise
    except json.JSONDecodeError:
        logging.critical("config.json is not a valid JSON file.")
        raise
    except Exception as e:
        logging.critical(f"An unexpected error occurred while loading config.json: {e}")
        raise

config = load_config()
matrix_homeserver = config["matrix_homeserver"]
matrix_user_id = config["matrix_user_id"]
matrix_password = config["matrix_password"]
wigle_api_key = config["wigle_api_key"]

class WigleBot:
    def __init__(self):
        self.store_path = "store/"  # Path to store sync tokens and other state
        self.client = nio.AsyncClient(
            matrix_homeserver,
            matrix_user_id,
            store_path=self.store_path
        )
        self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=60))
        self.wigle_api_key = wigle_api_key
        self.command_prefix = "!"  # Define a command prefix for bot commands

    async def start(self):
        # Create the store directory if it doesn't exist
        if not os.path.exists(self.store_path):
            os.makedirs(self.store_path)

        # Log in with username and password
        logging.info("Logging in with username and password.")
        login_response = await self.client.login(matrix_password)
        if isinstance(login_response, nio.LoginError):
            logging.error(f"Failed to log in: {login_response.message}")
            return
        else:
            logging.info("Login successful.")

        self.client.add_event_callback(self.message_callback, nio.RoomMessageText)
        self.client.add_event_callback(self.invite_callback, nio.InviteEvent)

        # Start syncing with the server
        await self.client.sync_forever(timeout=30000)

    async def close(self):
        await self.session.close()
        await self.client.close()

    async def message_callback(self, room, event):
        # Ignore messages from ourselves
        if event.sender == self.client.user_id:
            return

        # Check if the message is a command
        if event.body.startswith(self.command_prefix):
            command_body = event.body[len(self.command_prefix):].strip()
            command_parts = command_body.split()
            command = command_parts[0].lower()
            args = command_parts[1:]

            if command == "user" and args:
                username = args[0]
                logging.info(f"Command 'user' invoked for username: {username}")
                await self.send_typing_notice(room.room_id)
                response = await self.fetch_wigle_user_stats(username)
                if "success" in response and response["success"]:
                    message = self.create_user_message(response)
                    await self.send_message(room.room_id, message)
                else:
                    error_message = response.get("message", "Failed to fetch user stats.")
                    logging.warning(f"WiGLE user stats fetch error for {username}: {error_message}")
                    await self.send_message(room.room_id, error_message)
            elif command == "grouprank":
                logging.info("Command 'grouprank' invoked.")
                await self.send_typing_notice(room.room_id)
                response = await self.fetch_wigle_group_rank()
                if "success" in response and response["success"]:
                    message = self.format_group_rankings(response["groups"])
                    await self.send_message(room.room_id, message)
                else:
                    error_message = response.get("message", "Failed to fetch group ranks.")
                    logging.warning(f"WiGLE group rank fetch error: {error_message}")
                    await self.send_message(room.room_id, error_message)
            elif command == "userrank" and args:
                group = " ".join(args)
                logging.info(f"Command 'userrank' invoked for group: {group}")
                await self.send_typing_notice(room.room_id)
                response = await self.fetch_wigle_id(group)
                if "success" in response and response["success"]:
                    url = response.get("url")
                    group_data = await self.fetch_user_rank(url)
                    if group_data:
                        message = self.format_user_rankings(group_data.get("users", []), group)
                        await self.send_message(room.room_id, message)
                    else:
                        await self.send_message(room.room_id, "Failed to fetch group data.")
                else:
                    error_message = response.get("message", "Failed to fetch group ID.")
                    logging.warning(f"WiGLE group ID fetch error for {group}: {error_message}")
                    await self.send_message(room.room_id, error_message)
            elif command == "alltime":
                logging.info("Command 'alltime' invoked.")
                await self.send_typing_notice(room.room_id)
                response = await self.fetch_wigle_alltime_rank()
                if "success" in response and response["success"]:
                    message = self.format_alltime_rankings(response["results"])
                    await self.send_message(room.room_id, message)
                else:
                    error_message = response.get("message", "Failed to fetch user ranks.")
                    logging.warning(f"WiGLE all-time rank fetch error: {error_message}")
                    await self.send_message(room.room_id, error_message)
            elif command == "monthly":
                logging.info("Command 'monthly' invoked.")
                await self.send_typing_notice(room.room_id)
                response = await self.fetch_wigle_month_rank()
                if "success" in response and response["success"]:
                    message = self.format_monthly_rankings(response["results"])
                    await self.send_message(room.room_id, message)
                else:
                    error_message = response.get("message", "Failed to fetch monthly rankings.")
                    logging.warning(f"WiGLE monthly rank fetch error: {error_message}")
                    await self.send_message(room.room_id, error_message)
            elif command == "help":
                logging.info("Command 'help' invoked.")
                await self.send_typing_notice(room.room_id)
                message = self.get_help_message()
                await self.send_message(room.room_id, message)
            else:
                # Unknown command
                await self.send_message(room.room_id, "Unknown command. Type !help for available commands.")

    async def send_message(self, room_id, message):
        content = {
            "msgtype": "m.text",
            "body": message
        }
        await self.client.room_send(
            room_id,
            message_type="m.room.message",
            content=content
        )

    async def send_typing_notice(self, room_id):
        await self.client.room_typing(room_id, timeout=3000)

    async def invite_callback(self, room, event):
        await self.client.join(room.room_id)
        logging.info(f"Joined room {room.room_id}")

    async def fetch_wigle_user_stats(self, username: str):
        timestamp = int(time.time())
        req = f"https://api.wigle.net/api/v2/stats/user?user={username}&nocache={timestamp}"
        headers = {
            "Authorization": f"Basic {self.wigle_api_key}",
            "Cache-Control": "no-cache",
        }
        try:
            async with self.session.get(req, headers=headers) as response:
                if response.status == 404:
                    logging.info(f"WiGLE user {username} not found.")
                    return {"success": False, "message": "User not found."}
                elif response.status != 200:
                    logging.error(f"Error fetching WiGLE user stats for {username}: {response.status}")
                    return {"success": False, "message": f"HTTP error {response.status}"}

                data = await response.json()
                if data.get("success") and "statistics" in data and "userName" in data["statistics"]:
                    if data["statistics"]["userName"].lower() == username.lower():
                        logging.info(f"Fetched WiGLE user stats for {username}")
                        image_url = data.get("imageBadgeUrl", "")
                        if image_url:
                            image_url += f"?nocache={timestamp}"
                            data["imageBadgeUrl"] = image_url
                        return data
                    else:
                        return {"success": False, "message": "User not found."}
                else:
                    return {"success": False, "message": "Invalid data received or user not found."}
        except Exception as e:
            logging.error(f"Failed to fetch WiGLE user stats for {username}: {e}")
            return {"success": False, "message": str(e)}

    async def fetch_wigle_group_rank(self):
        timestamp = int(time.time())
        req = f"https://api.wigle.net/api/v2/stats/group?nocache={timestamp}"
        headers = {
            "Authorization": f"Basic {self.wigle_api_key}",
            "Cache-Control": "no-cache",
        }
        try:
            async with self.session.get(req, headers=headers) as response:
                if response.status != 200:
                    logging.error(f"Error fetching WiGLE group ranks: {response.status}")
                    return {"success": False, "message": f"HTTP error {response.status}"}

                data = await response.json()
                if data.get("success") and "groups" in data:
                    return data
                else:
                    return {"success": False, "message": "No group data available."}
        except Exception as e:
            logging.error(f"Failed to fetch WiGLE group ranks: {e}")
            return {"success": False, "message": str(e)}

    async def fetch_wigle_id(self, group_name: str):
        timestamp = int(time.time())
        req = f"https://api.wigle.net/api/v2/stats/group?nocache={timestamp}"
        headers = {
            "Authorization": f"Basic {self.wigle_api_key}",
            "Cache-Control": "no-cache",
        }
        try:
            async with self.session.get(req, headers=headers) as response:
                if response.status != 200:
                    logging.error(f"Error fetching WiGLE group ID for '{group_name}': {response.status}")
                    return {"success": False, "message": f"HTTP error {response.status}"}

                data = await response.json()
                if data.get("success"):
                    groups = data.get("groups", [])
                    for group in groups:
                        if group["groupName"].lower() == group_name.lower():
                            group_id = group["groupId"]
                            url = f"https://api.wigle.net/api/v2/group/groupMembers?groupid={group_id}"
                            return {"success": True, "groupId": group_id, "url": url}

                    return {"success": False, "message": f"No group named '{group_name}' found."}
                else:
                    logging.warning(f"WiGLE group ID fetch error for '{group_name}': {data['message']}")
                    return {"success": False, "message": data["message"]}
        except Exception as e:
            logging.error(f"Failed to fetch WiGLE group ID for '{group_name}': {e}")
            return {"success": False, "message": str(e)}

    async def fetch_user_rank(self, url: str):
        try:
            headers = {
                "Authorization": f"Basic {self.wigle_api_key}",
                "Cache-Control": "no-cache",
            }
            async with self.session.get(url, headers=headers) as response:
                if response.status != 200:
                    logging.error(f"Error fetching user rank from URL: {url}, HTTP error {response.status}")
                    return None

                data = await response.json()
                return data
        except Exception as e:
            logging.error(f"Failed to fetch user rank from URL: {url}, {e}")
            return None

    async def fetch_wigle_alltime_rank(self):
        req = f"https://api.wigle.net/api/v2/stats/standings?sort=discovered&pagestart=0"
        headers = {
            "Authorization": f"Basic {self.wigle_api_key}",
            "Cache-Control": "no-cache",
        }
        try:
            async with self.session.get(req, headers=headers) as response:
                if response.status != 200:
                    logging.error(f"Error fetching WiGLE user ranks: {response.status}")
                    return {"success": False, "message": f"HTTP error {response.status}"}

                data = await response.json()
                if data.get("success") and "results" in data:
                    data["results"] = [result for result in data["results"] if result["userName"] != "anonymous"]
                    return data
                else:
                    return {"success": False, "message": "No rank data available."}
        except Exception as e:
            logging.error(f"Failed to fetch WiGLE user ranks: {e}")
            return {"success": False, "message": str(e)}

    async def fetch_wigle_month_rank(self):
        req = f"https://api.wigle.net/api/v2/stats/standings?sort=monthcount&pagestart=0"
        headers = {
            "Authorization": f"Basic {self.wigle_api_key}",
            "Cache-Control": "no-cache",
        }
        try:
            async with self.session.get(req, headers=headers) as response:
                if response.status != 200:
                    logging.error(f"Error fetching WiGLE monthly ranking: {response.status}")
                    return {"success": False, "message": f"HTTP error {response.status}"}

                data = await response.json()
                if data.get("success") and "results" in data:
                    data["results"] = [result for result in data["results"] if result["userName"] != "anonymous"]
                    return data
                else:
                    return {"success": False, "message": "No rank data available."}
        except Exception as e:
            logging.error(f"Failed to fetch WiGLE monthly ranking: {e}")
            return {"success": False, "message": str(e)}

    def create_user_message(self, response):
        statistics = response["statistics"]
        username = response["user"]
        rank = response["rank"]
        monthRank = response["monthRank"]
        prevRank = statistics["prevRank"]
        prevMonthRank = statistics["prevMonthRank"]
        eventMonthCount = statistics["eventMonthCount"]
        eventPrevMonthCount = statistics["eventPrevMonthCount"]
        discoveredWiFiGPS = statistics["discoveredWiFiGPS"]
        discoveredWiFiGPSPercent = statistics["discoveredWiFiGPSPercent"]
        discoveredWiFi = statistics["discoveredWiFi"]
        discoveredCellGPS = statistics["discoveredCellGPS"]
        discoveredCell = statistics["discoveredCell"]
        discoveredBtGPS = statistics["discoveredBtGPS"]
        discoveredBt = statistics["discoveredBt"]
        totalWiFiLocations = statistics["totalWiFiLocations"]
        last = statistics["last"]
        first = statistics["first"]

        # Format dates
        last_event_date_str, _ = last.split("-")
        first_event_date_str, _ = first.split("-")
        last_event_datetime = datetime.strptime(last_event_date_str, "%Y%m%d")
        first_event_datetime = datetime.strptime(first_event_date_str, "%Y%m%d")
        last_event_formatted = last_event_datetime.strftime("%B %d, %Y")
        first_event_formatted = first_event_datetime.strftime("%B %d, %Y")

        message = (
            f"**WiGLE User Stats for '{username}'**\n"
            f"Username: {username}\n"
            f"Rank: {rank:,}\n"
            f"Previous Rank: {prevRank:,}\n"
            f"Monthly Rank: {monthRank:,}\n"
            f"Last Month's Rank: {prevMonthRank:,}\n"
            f"Events This Month: {eventMonthCount:,}\n"
            f"Last Month's Events: {eventPrevMonthCount:,}\n"
            f"Discovered WiFi GPS: {discoveredWiFiGPS:,}\n"
            f"Discovered WiFi GPS Percent: {discoveredWiFiGPSPercent}\n"
            f"Discovered WiFi: {discoveredWiFi:,}\n"
            f"Discovered Cell GPS: {discoveredCellGPS:,}\n"
            f"Discovered Cell: {discoveredCell:,}\n"
            f"Discovered BT GPS: {discoveredBtGPS:,}\n"
            f"Discovered BT: {discoveredBt:,}\n"
            f"Total WiFi Locations: {totalWiFiLocations:,}\n"
            f"Last Event: {last_event_formatted}\n"
            f"First Ever Event: {first_event_formatted}\n"
        )
        return message

    def format_group_rankings(self, groups):
        p = inflect.engine()
        rankings = "**WiGLE Group Rankings:**\n"
        for i, group in enumerate(groups[:10], start=1):
            groupName = group["groupName"]
            discovered = group["discovered"]
            formatted_discovered = "{:,}".format(discovered)
            rank = p.ordinal(i)
            rankings += f"{rank}: {groupName} | Total: {formatted_discovered}\n"
        return rankings

    def format_user_rankings(self, users, group_name):
        p = inflect.engine()
        rankings = f"**User Rankings for '{group_name}':**\n"
        filtered_users = [user for user in users if "L" not in user["status"]]
        for i, user in enumerate(filtered_users[:10], start=1):
            username = user["username"]
            discovered = user["discovered"]
            rank = p.ordinal(i)
            discovered_formatted = "{:,}".format(discovered)
            rankings += f"{rank}: {username} | Total: {discovered_formatted}\n"
        return rankings

    def format_alltime_rankings(self, results):
        p = inflect.engine()
        rankings = "**WiGLE All-Time User Rankings:**\n"
        for i, result in enumerate(results[:10], start=1):
            userName = result["userName"]
            discoveredWiFiGPS = result["discoveredWiFiGPS"]
            rank = p.ordinal(i)
            formatted_discoveredWiFiGPS = "{:,}".format(discoveredWiFiGPS)
            rankings += f"{rank}: {userName} | Total: {formatted_discoveredWiFiGPS}\n"
        return rankings

    def format_monthly_rankings(self, results):
        p = inflect.engine()
        rankings = "**WiGLE Monthly User Rankings:**\n"
        for i, result in enumerate(results[:10], start=1):
            userName = result["userName"]
            eventMonthCount = result["eventMonthCount"]
            rank = p.ordinal(i)
            rankings += f"{rank}: {userName} | Total: {eventMonthCount:,}\n"
        return rankings

    def get_help_message(self):
        help_text = (
            "**Command List**\n"
            "`!user <username>` - Get stats for a WiGLE user.\n"
            "`!grouprank` - Get WiGLE group rankings.\n"
            "`!userrank <groupname>` - Get WiGLE user rankings for a group.\n"
            "`!alltime` - Get WiGLE All-Time user rankings.\n"
            "`!monthly` - Get WiGLE monthly user rankings.\n"
            "`!help` - Shows this help message.\n"
        )
        return help_text

# Main execution

async def main():
    bot = WigleBot()
    try:
        await bot.start()
    except Exception as e:
        logging.error(f"An error occurred while running the bot: {e}")
    finally:
        await bot.close()

if __name__ == "__main__":
    asyncio.run(main())
