import os

import discord

from dotenv import load_dotenv

from discord.ext import commands

import random

import sqlite3

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
GUILD = os.getenv('DISCORD_GUILD')

bot = commands.Bot(command_prefix=';')

conn = sqlite3.connect('moviekarma.db')
c = conn.cursor()

reactions = ['👍', '🔥', '🍆', '💦', '😤', '👁️','👄','🔫', '🇰🇵']
messages_good = ["I love you Joe!", "I'll never leave you Joe!", "Do you remember our first date Joe?", "Your soul belongs to me Joe!", "If you leave me Joe, I'll hurt you!", "I hope you're happy Joe", "This made me uncomfortable to write Joe"]
messages_bad = ["You're not Joe!", "I hate you! Where's Joe?", "Give me Joe!"]

"""
MAKE SURE MY KARMA IS AT 1
TALLY FOR RATING SEEMS VERY IFFY
EMBED
"""

@bot.event
async def on_ready():
	print("MovieKarma activated.")
	c.execute('CREATE TABLE IF NOT EXISTS users (user_id int, karma int DEFAULT 0)')
	c.execute('CREATE TABLE IF NOT EXISTS movies (title varchar(255), nickname varchar(255), user_id int, voting_enabled int DEFAULT 1, vote_result varchar(255))')
	c.execute('CREATE TABLE IF NOT EXISTS votes (movie_id int, user_id int, vote_value int)')
	c.execute('CREATE TABLE IF NOT EXISTS polls (message_id int, poll_creator int, is_active int, movie_id int)')
	c.execute('CREATE TABLE IF NOT EXISTS meme (joe_id int)')

	conn.commit()
	random.shuffle(reactions)

@bot.command(name='addmovie', help='Adds movie to list', aliases=['add'])
async def add_movie(ctx, movie_title):
	c.execute('SELECT title from movies')
	titles = c.fetchall()
	titles = [item[0].lower() for item in titles]
	if not movie_title.lower() in titles:
		recommender_id = ctx.message.author.id
		c.execute('SELECT * FROM users WHERE user_id=?', (recommender_id,))
		if not c.fetchone():
			start(recommender_id)
		c.execute('SELECT * FROM movies ORDER BY rowid desc')
		row = c.fetchone()
		c.execute('INSERT INTO movies (title, user_id) VALUES (?, ?)', (movie_title, recommender_id))
		conn.commit()
		c.execute('SELECT rowid FROM movies WHERE title=?', (movie_title,))
		ID = c.fetchone()[0]
		await ctx.send("**{0}** added to list (ID: {1})".format(movie_title, ID))
	else:
		await ctx.send("**{0}** is already in the list".format(movie_title))

@bot.command(name='listmovies', help='Lists movies', aliases=['list'])
async def list_movies(ctx, page_num: int = 1, user: discord.User = None):
	print(ctx.message.author.id)
	server = ctx.message.guild
	messageblock = '```'
	offset = 20 * (page_num-1)
	if user:
		for row in c.execute('SELECT rowid, title, user_id, vote_result FROM movies WHERE user_id = ? ORDER BY rowid LIMIT ?, 20', (user.id, offset)):
			#print(row)
			nickname = server.get_member(row[2]).display_name
			if row[3]:
				messageblock += "{0}, {1} - {2}, Verdict: {3}\n".format(row[0], row[1], nickname, row[3])
			else:
				messageblock += "{0}, {1} - {2}\n".format(row[0], row[1], nickname)
	else:
		for row in c.execute('SELECT rowid, title, user_id, vote_result FROM movies ORDER BY rowid LIMIT ?, 20', (offset,)):
			#print(row)
			nickname = server.get_member(row[2]).display_name
			if row[3]:
				messageblock += "{0}, {1} - {2}, Verdict: {3}\n".format(row[0], row[1], nickname, row[3])
			else:
				messageblock += "{0}, {1} - {2}\n".format(row[0], row[1], nickname)
	messageblock += '```'
	await ctx.send(messageblock)

@bot.command(name='search', help='Checks if movie is in the list already')
async def search(ctx, movie_title):
	c.execute('SELECT title, user_id from movies WHERE title = ?', (movie_title,))
	row = c.fetchone()
	if row:
		server = ctx.message.guild
		nickname = server.get_member(row[1]).display_name
		await ctx.send("**{0}** was already added by **{1}**".format(row[0], nickname))
	else:
		await ctx.send("**{0}** is probably not in the list yet. If your capitalization differs from the title in the list this command won't work properly".format(movie_title))

@bot.command(name='legacy', help='Lists all movies previously voted on')
async def list_legacy(ctx, page_num: int = 1):
	server = ctx.message.guild
	messageblock = '```'
	offset = 20 * (page_num-1)
	for row in c.execute('SELECT rowid, title, user_id, vote_result FROM movies WHERE vote_result IS NOT NULL ORDER BY rowid LIMIT ?, 20', (offset,)):
		#print(row)
		nickname = server.get_member(row[2]).display_name
		messageblock += "{0}, {1} - {2}, Verdict: {3}\n".format(row[0], row[1], nickname, row[3])
	messageblock += '```'
	await ctx.send(messageblock)

# need to add weights based on karma
@bot.command(name='lottery', help='Chooses a random movie', aliases=['roll'])
async def roll_movie(ctx, count: int = None):
	server = ctx.message.guild
	options = []
	for row in c.execute('SELECT rowid, title FROM movies WHERE voting_enabled=1'):
		options.append((row[1], "ID: {0}".format(row[0])))
	if not count or count == 1:
		choice = random.choice(options)
		c.execute('SELECT user_id, rowid FROM movies WHERE title=?', (choice,))
		sponsor_id = c.fetchone()
		sponsor = server.get_member(sponsor_id[0]).display_name
		ID = sponsor_id[1]
		await ctx.send("Your movie is **{0}**! Sponsored by **{1}**! (ID: {2})".format(choice, sponsor, ID))
	elif count > 9:
			await ctx.send("Poll is too large. Only supports sizes of 9 or less")
			return
	else:
		choices = random.sample(options, k=count)
		messageblock = 'Your movie options are:\n'
		for index, choice in enumerate(choices):
			messageblock += '{0}: **{1}** ({2})\n'.format(reactions[index], choice[0], choice[1])
		messageblock += 'Vote using the reactions below!'
		react_message = await ctx.send(messageblock)
		c.execute('INSERT INTO polls VALUES (?, ?, ?, ?)', (react_message.id, ctx.message.author.id, 1, -1))
		conn.commit()
		for reaction in reactions[:count]:
			await react_message.add_reaction(reaction)

@bot.command(name='tally', help='Tallies votes from a multi-roll or rating')
async def tally_votes(ctx):
	c.execute('SELECT message_id, movie_id FROM polls WHERE poll_creator = ? AND is_active = 1', (ctx.message.author.id,))
	row = c.fetchone()
	if not row:
		await ctx.send("You have no active votes!")
		return
	msg_id = row[0]
	movie_id = row[1]

	if movie_id == -1:
		server = ctx.message.guild
		message = await ctx.message.channel.fetch_message(msg_id)
		options = [x.replace('*','').strip() for x in message.content.split('\n')]
		options = options[1:len(options)-1]
		option_dict = {x[:1]: x[2:] for x in options}

		tally = {x:-1 for x in option_dict.keys()}
		for reaction in message.reactions:
			if reaction.emoji in option_dict.keys():
				reactors = await reaction.users().flatten()
				for reactor in reactors:
					tally[reaction.emoji] += 1
		
		#max_vote = max(tally, key=lambda key: tally[key])
		max_vote = max(tally.values())
		top_movies = [k for k, v in tally.items() if v == max_vote]
		winner = random.choice(top_movies)
		result = option_dict[winner]
		# this is so fucking bad
		result = result.split('(ID:')
		title = result[0].strip()
		id_chunk = result[1]
		c.execute('SELECT user_id FROM movies WHERE title = ?', (title,))
		nickname = server.get_member(c.fetchone()[0]).display_name
		await ctx.send('**{0}** emerges victorious! (ID:{1} You can thank **{2}** now'.format(title, id_chunk, nickname))
		c.execute('UPDATE polls SET is_active = 0 WHERE message_id = ?', (msg_id,))
		conn.commit()
	else:
		overall_score = 0
		message = await ctx.message.channel.fetch_message(msg_id)
		options = ['👍', '👎']
		voters = [ctx.me.id]

		tally = {x:0 for x in options}
		for reaction in message.reactions:
			if reaction.emoji in options:
				reactors = await reaction.users().flatten()
				for reactor in reactors:
					if reactor.id not in voters:
						tally[reaction.emoji] += 1
						voters.append(reactor.id)

		overall_score = tally['👍'] - tally['👎']
		c.execute('SELECT karma FROM users WHERE user_id = ?', (ctx.message.author.id,))
		karma = c.fetchone()[0]
		return_msg = ''
		if overall_score > 0:
			return_msg = "**GOOD MOVIE** (+{0})".format(overall_score)
			karma += 1
		elif overall_score < 0:
			return_msg = "**BAD MOVIE** ({0})".format(overall_score)
			karma -= 1
		else:
			return_msg = "**TIE VOTE** (0)" 
		await ctx.send("Result: {0}".format(return_msg))

		c.execute('UPDATE users SET karma = ? WHERE user_id = ?', (karma, ctx.message.author.id))
		result = '{0} {1}'.format(return_msg.split(' ')[0][2:], return_msg.split(' ')[2])
		c.execute('UPDATE movies SET vote_result = ? WHERE rowid = ?', (result, movie_id))
		c.execute('UPDATE polls SET is_active = 0 WHERE message_id = ?', (msg_id,))
		conn.commit()
		await ctx.send("Karma has been awarded to **{0}**".format(ctx.message.author.display_name))

#DONT UNCOMMENT
# @bot.command(name="f")
# async def tally2(ctx):
# 	c.execute('UPDATE movies SET voting_enabled = 0 WHERE rowid = ?', (56,))
# 	c.execute('UPDATE users SET karma = 1 WHERE user_id = ?', (691050778940538880,))
# 	c.execute('DROP TABLE polls')
# 	await ctx.send("Result: **GOOD MOVIE** (+5)")
# 	await ctx.send("Karma has been awarded to **{0}**".format(ctx.message.author.display_name))

@bot.command(name="startvote", help="Start voting for specified movie", aliases=['start'])
async def start_voting(ctx, movie_id):
	c.execute('SELECT title, user_id, voting_enabled FROM movies WHERE rowid = ?', (movie_id,))
	row = c.fetchone()
	if not row:
		await ctx.send("Movie with ID {0} does not exist".format(movie_id))
		return
	title = row[0]
	uid = row[1]
	enabled = row[2]
	server = ctx.message.guild
	if uid != ctx.message.author.id:
		await ctx.send("Only **{0}** can start voting for **{1}**!".format(server.get_member(uid).display_name, title))
		return
	if enabled == 0:
		await ctx.send("This movie has already been voted for!")
		return
	react_message = await ctx.send("Vote for **{0}** here!".format(title))
	await react_message.add_reaction('👍')
	await react_message.add_reaction('👎')
	c.execute('UPDATE movies SET voting_enabled = 0 WHERE rowid = ?', (movie_id,))
	c.execute('INSERT INTO polls VALUES (?, ?, ?, ?)', (react_message.id, uid, 1, movie_id))
	conn.commit()

# @bot.command(name="vote", help="Vote on a movie")
# async def vote(ctx, movie_id, verdict: str = None):
# 	c.execute('SELECT * FROM movies WHERE rowid = ?', (movie_id,))
# 	if c.fetchone():
# 		user_id = ctx.message.author.id
# 		c.execute('SELECT * FROM votes WHERE movie_id = ? and user_id = ?', (movie_id, user_id))
# 		has_voted = c.fetchone()
# 		if verdict:
# 			if not has_voted:
# 				vote_val = 0
# 				verdict = verdict.lower()
# 				if verdict == 'good':
# 					vote_val = 1
# 					c.execute('INSERT INTO votes (movie_id, user_id, vote_value) VALUES (?, ?, ?)', (movie_id, user_id, vote_val))
# 					await ctx.send("Vote accepted")
# 				elif verdict == 'bad':
# 					vote_val = -1
# 					c.execute('INSERT INTO votes (movie_id, user_id, vote_value) VALUES (?, ?, ?)', (movie_id, user_id, vote_val))
# 					await ctx.send("Vote accepted")
# 				else:
# 					await ctx.send("Your vote needs to be 'good' or 'bad'")
# 				conn.commit()
# 			else:
# 				await ctx.send("You have already voted for this movie")
# 		else:
# 			await ctx.send("Please enter your vote (good or bad)")
# 	else:
# 		await ctx.send("Movie with ID {0} does not exist".format(movie_id))

# outdated. removed nickname from movies in case ressurection is required 
# @bot.command(name="endvote", help="Stop voting for specified movie", aliases=['end'])
# async def end_voting(ctx, movie_id: int = None):
# 	c.execute('SELECT nickname FROM movies where rowid=?', (movie_id,))
# 	nick = c.fetchone()[0]
# 	if nick == ctx.message.author.display_name:
# 		if movie_id:
# 			c.execute('SELECT voting_enabled FROM movies WHERE rowid=?', (movie_id,))
# 			if c.fetchone()[0] == 1:
# 				c.execute('UPDATE movies SET voting_enabled=0 WHERE rowid=?', (movie_id,))
# 				conn.commit()
# 				c.execute('SELECT SUM(vote_value) FROM votes WHERE movie_id=?', (movie_id,))
# 				#print(c.fetchone())
# 				vote_result = c.fetchone()[0]
# 				if vote_result == None:
# 					vote_result = 0
# 				c.execute('SELECT title FROM movies WHERE rowid=?', (movie_id,))
# 				await ctx.send("Voting has been stopped for {0}".format(c.fetchone()[0]))
# 				return_msg = ''
# 				if vote_result > 0:
# 					return_msg = "**GOOD MOVIE** (+{0})".format(vote_result)
# 				elif vote_result < 0:
# 					return_msg = "**BAD MOVIE** ({0})".format(vote_result)
# 				else:
# 					return_msg = "**TIE VOTE** (0)"
# 				await ctx.send("Result: {0}".format(return_msg))
# 				c.execute('SELECT movies.nickname, movies.user_id, users.karma FROM movies INNER JOIN users ON movies.user_id=users.user_id WHERE movies.rowid=?',(movie_id,))
# 				row_returned = c.fetchone()
# 				name = row_returned[0]
# 				name_id = row_returned[1]
# 				karma = row_returned[2]+1
# 				c.execute('UPDATE users SET karma=? WHERE user_id=?', (karma, name_id))
# 				res = "{0} {1}".format(return_msg.split(' ')[0][2:], return_msg.split(' ')[2])
# 				c.execute('UPDATE movies SET vote_result=? WHERE rowid=?', (res, movie_id))
# 				conn.commit()
# 				await ctx.send("Karma has been awarded to **{0}**".format(name))
# 			else:
# 				await ctx.send("Voting for this movie has already ended")
# 		else:
# 			await ctx.send("Enter the ID of the movie you wish to end voting for")
# 	else:
# 		await ctx.send("Only the person who added this movie can end voting")

@bot.command(name="showkarma", help="Lists all users and karma", aliases=['karma'])
async def show_karma(ctx):
	server = ctx.message.guild
	messageblock = '```'
	for row in c.execute('SELECT * FROM users'):
		messageblock += 'User: {0}, Karma: {1}\n'.format(server.get_member(row[0]).display_name, row[1])
	messageblock += '```'
	await ctx.send(messageblock)

@bot.command(name="remove", help="Removes movie from list given ID", aliases=['delete'])
async def remove_movie(ctx, movie_id):
	server = ctx.message.guild
	c.execute('SELECT user_id, title FROM movies where rowid=?', (movie_id,))
	row = c.fetchone()
	nick = server.get_member(row[0]).display_name
	title = row[1]
	if nick == ctx.message.author.display_name:
		c.execute('DELETE FROM movies WHERE rowid=?', (movie_id,))
		conn.commit()
		await ctx.send("**{0}** was removed from the list".format(title))
	else:
		await ctx.send("Only **{0}** can delete **{1}**".format(nick, title))

@bot.command(name="wall-e", help="fuck you")
async def stupid(ctx):
	await ctx.send("Wow you rolled **Wall-e**. Crazy how that works.")
	await ctx.send('░░░░░░░░░░░░░░░░░░░░░░░░░░░\n \
░░░░░░░░░░▄▄▄▄▄▄▄░░░░░░░░░░\n \
░░░░░░▄▄▀▀░░░░░░░▀▀▄▄░░░░░░\n \
░░░░▄▀░░░░░░░░░░░░░░░▀▄░░░░\n \
░░░▄▀░░░▄▄▄▄▄▄▄▄▄▄▄░░░░█░░░\n \
░░█░░▄███████████████▄░░█░░\n \
░█░░▄██▀░▄▄▀███▀▄▄░▀███░░█░\n \
░█░░▀█████████████████▀░░█░\n \
░█░░░░▀▀████████████▀░░░░█░\n \
░░█░░░░░░░░▀▀▀▀▀░░░░░░░▄▀░░\n \
░░░▀▀▄▄▄▄░░░░░░░░░▄▄▄▀▀░░░░\n \
░░▄██▀▄▄▄█▀▀▀▀▀▀▀█▄▄▄▀██▄░░\n \
░▄▀██░░░░░▀▀▀▀▀▀▀░░░░░██▀▄░\n \
█░░██░░░░░░░░░░░░░░░░░██░░█\n \
█░░██░░░░░░░░░░░░░░░░░██░░█\n \
█░░██░░░░░░░░░░░░░░░░░██░░█\n \
█░░██░░░░░░░░░░░░░░░░░██░░█\n \
█░░██░░░░░░░░░░░░░░░░░██░░█\n \
█░░██▄░░░░░░░░░░░░░░░▄██░░█\n \
▀▀▄█░█▄▄▄▄░░░░░░░▄▄▄▄█░█▄▀▀\n \
░░░░░░░░░█▄▄▄▄▄▄▄█░░░░░░░░░\n \
░░░░░░░░░░░░░░░░░░░░░░░░░░░')

@bot.command(name="girlfriend", help="I love Joe", aliases=['gf'])
async def girlfriend_sim(ctx):
	# setup
	# c.execute('INSERT INTO meme (joe_id) VALUES (?)', (ctx.message.author.id,))
	# conn.commit()
	c.execute('SELECT joe_id FROM meme')
	row = c.fetchone()
	joe = row[0]
	if ctx.message.author.id == joe:
		message = random.choices(messages_good, weights=[.166,.166,.166,.166,.166,.166,.004])
		print(message[0])
		await ctx.send(message[0])
	else:
		message = random.choice(messages_bad)
		await ctx.send(message)

#helpers
def start(ID):
	c.execute('INSERT INTO users (user_id) VALUES (?)', (ID,))

bot.run(TOKEN)