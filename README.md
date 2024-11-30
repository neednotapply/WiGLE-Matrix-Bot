<h1 align="center">:satellite: WiGLE Matrix Bot :satellite:</h1>

<p align="center">
  <img src="https://i.imgur.com/CRKolzB.jpg">
</p>

This Matrix bot is used to pull stats from [WiGLE](https://wigle.net/) using WiGLE's API as shown below.

## Variables
Prior to using the bot the following variables must be changed in the `config.json` file:
- Replace `@your_bot_username:matrix.org` with your Matrix bot's username
- Replace `your_bot_password` with your Matrix bot's password
- Adjust the homeserver_url appropriately if the bot will not belong to the default https://matrix.org federation.

  - If you do not know how to create a Matrix bot, instructions on how to do so can be found [here](https://matrix-nio.readthedocs.io/en/latest/#)
- Replace `YOUR-ENCODED-FOR-USE-KEY-HERE` with your WiGLE API Key.
  - Your API key can be found [here](https://api.wigle.net/), select your account page in the lower right, then select "Show My Token".
  - The token you are looking for will be listed as the "Encoded for use".

## Commands
Once the above variables have been updated, run the bot using the following commands:
- `!user` followed by a username to get user stats. For example, `/user neednotapply`.
- `!userrank` followed by a group name to get user rankings for that group. For example, `/userrank #wardriving`.
- `!grouprank` to show group rankings.
- `!alltime` for all-time user rankings.
- `!monthly` for monthly user rankings.
- `!help` to show a list of available bot commands.

## Credits
Discord bot created by [Kavitate](https://github.com/Kavitate).  
Further development of this bot is in collaboration with [RocketGod](https://github.com/RocketGod-git).  
Modified for Matrix ecosystem by [NeedNotApply](https://github.com/neednotapply).

The idea for this bot was inspired by the [WiGLE Bot Repo](https://github.com/INIT6Source/WiGLE-bot) made by [INIT6Source](https://github.com/INIT6Source).
