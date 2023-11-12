import re
import feedparser
import sys
import tldextract
from datetime import datetime
import hashlib
import pandas as pd
from bs4 import BeautifulSoup
from collections import Counter
from configparser import ConfigParser
import base64
import dateutil
import requests
from dateutil.parser import *
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.firefox_profile import FirefoxProfile
from selenium.webdriver.firefox.firefox_binary import FirefoxBinary
from selenium.common.exceptions import TimeoutException

create_local_report = "N"
create_remote_report = "Y"
use_accordion = "Y" # this can be N in most cases
publish_threshold = 2
remote_name = "./results/local"

feed_source = ['https://www.politifact.com/rss/all/', 'https://www.factcheck.org/feed/', 'https://leadstories.com/atom.xml', 'https://www.snopes.com/feed']
page_source = ['https://www.reuters.com/fact-check/', 'https://www.usatoday.com/news/factcheck/']  

old_source = "./results/published_stories.csv"
results_output = './results/stories.csv'

published_domain = "https://www.flammablepants.com/"

creds = "creds/creds.ini"

#Read creds.ini file
config = ConfigParser()
config.read(creds)
#Get options for details to include in summaries, and file format export options
creds = config["WORDPRESS"]
url_post = creds["url_post"]
url_media = creds["url_media"]
user = creds["username"]
password = creds["password"]

d = datetime.now()
year = d.strftime("%Y")
month = d.strftime("%m")
day = d.strftime("%d")
hour = d.strftime("%H")
minute = d.strftime("%M")
second = d.strftime("%S")
now_oclock = f'{month}-{day}-{year} {hour}:{minute}:{second}'
now_human = f'{month}-{day}-{year} at {hour}:{minute}'
url_path = f'fact-check-{d.strftime("%B")}-{day}-{year}-at-{hour}{minute}{second}'
output_name = remote_name + "_" + year + "_" + month + "_" + day + "_" + hour + "_" + minute + ".html" 

blog_title = f'Collected Fact Checks on {d.strftime("%B")} {day}, {year} at {hour}:{minute}:{second}'

post_url = published_domain + url_path

df_source_raw = pd.DataFrame(columns = ['source', 'title', 'link', 'summary', 'published', 'guid', 'anchor'])
df_source_filtered = pd.DataFrame(columns = ['source', 'title', 'link', 'summary', 'published', 'guid', 'anchor', 'now'])
df_feeds = pd.DataFrame(columns = ['title', 'link', 'description', 'pubDate', 'guid'])

def clean_date(messy):

	tzmapping = {'CET': dateutil.tz.gettz('Europe/Berlin'),
             'CEST': dateutil.tz.gettz('Europe/Berlin'),
             'ET': dateutil.tz.gettz('America/New York')}

	dt = parse(messy, tzinfos=tzmapping)
	#print(dt)
	clean = dt.strftime('%m/%d/%Y %H:%M')

	return clean

def moar_hash(value):
	result = hashlib.md5(value.encode())
	sendback = result.hexdigest()

	return sendback

def text_cleanup(to_be_cleaned):
	cleansoup = BeautifulSoup(to_be_cleaned, 'lxml')
	cleaned = cleansoup.find('p')
	cleaned = cleaned.text

	return cleaned

def clean_string(messy_text):
	clean_text = re.sub('[^A-Za-z0-9]+', '_', messy_text)
	clean_text = clean_text.lower()
	return clean_text

def compress_text(squish):
	nospace = squish.replace('\r', '').replace('\n', '').replace(' ', '')
	nospace = ''.join(nospace.split())
	return nospace

def write_file(filename, content):
	with open(filename,'w') as output_file:
		output_file.write(content)

## Get to work

# driver profile
profile = webdriver.FirefoxProfile()
profile.set_preference("browser.cache.disk.enable", False)
profile.set_preference("browser.cache.memory.enable", False)
profile.set_preference("browser.cache.offline.enable", False)
profile.set_preference("network.http.use-cache", False) 

for fs in feed_source:
	try:
		print("\n* * *")
		print(f'parsing {fs}')
		feed = feedparser.parse(fs)
		source = feed['feed']['title']
		print(len(feed['entries']))
		if len(feed['entries']) > 0:
			for e in feed['entries']:
				title = e.title
				title_detail = e.title_detail
				links = e.links
				link = e.link
				summary = e.summary
				if fs == 'https://www.factcheck.org/feed/':
					summary = text_cleanup(summary)
				else:
					pass
				summary_detail = e.summary_detail
				published = e.published
				published = clean_date(published)
				published_parsed = e.published_parsed
				guid = e.id
				guidislink = e.guidislink
				anchor = moar_hash(link)
				df_source_raw.loc[df_source_raw.shape[0]] = [source, title, link, summary, published, guid, anchor]

		else:
			print(f'No items in {source}.')
	except:
		print(f'Something happened with {fs}')

driver = webdriver.Firefox(profile)
driver.set_page_load_timeout(90)

## Reuters
for ps in page_source:
	print(f'\n * Processing {ps}\n')
	driver.delete_all_cookies()
	try:
		driver.get(ps)
		resolved_url = driver.current_url
		temp_base = tldextract.extract(resolved_url) 
		dom = temp_base.domain
		suf = temp_base.suffix
		base_url = 'https://' + dom + '.' + suf
		soup=BeautifulSoup(driver.page_source, 'lxml')
		if ps == 'https://www.reuters.com/fact-check/':
			source = "Reuters"
			try:				
				main = soup.find('main')
				stories = main.find_all('li')
				for s in stories:
					#title = s.find('header', {'class' : 'header'}).contents
					title = s.find('header', {'class' : 'header'}).text
					summary = s.find('p').text
					base_one = s.find('div', {'data-story-id' : True})
					#print(f'\n{base_one.attrs}')
					guid = base_one['data-story-id']
					link = base_one['href']
					link = base_url + link
					base_time = s.find('time', {'datetime' : True})
					published = base_time['datetime'] 
					published = clean_date(published)
					anchor = moar_hash(link)
					df_source_raw.loc[df_source_raw.shape[0]] = [source, title, link, summary, published, guid, anchor]
			except:
				print("Reuters borkage")
		elif ps == 'https://www.usatoday.com/news/factcheck/':
			source = "USA Today"
			ti_list = []
			sum_list = []
			pub_list = []	
			lin_list = []
			try:				
				main = soup.find('div', {'gnt_pr'})
				# Get top level story
				try:
					story_header = main.find('a', {'gnt_m_he'})
					#print(story_header)
					title = story_header.text
					title = title.strip()
					summary = title
				except:
					print("No main story header")
				try:
					link = story_header.get('href')
					link = base_url + link
					base_time = story_header.find('div', {'data-c-dt' : True})
					published = base_time['data-c-dt']
				except:
					print("No main story link or published date")
				ti_list.append(title)
				sum_list.append(summary)
				pub_list.append(published)
				lin_list.append(link)

				# Get the rest of the stories
				main_sub = main.find('div', {'gnt_m'})
				stories = main_sub.find_all('a', limit=90)
				stories_datetime = main.find_all('div', {'gnt_m_flm_sbt'}, limit=90)
				for sdt in stories_datetime:
					try:
						published = sdt['data-c-dt']
					except:
						published = 'skip'
					pub_list.append(published)

				for s in stories:
					#print(f'\n\n{s}\n{s.attrs}')
					try:
						title = s.text
						title = title.strip()
						summary = s['data-c-br']
						link = s.get('href')
						link = base_url + link
						ti_list.append(title)
						sum_list.append(summary)
						lin_list.append(link)
					except:
						print("No 's in stories' information")

				check = len(ti_list)
				if check == len(sum_list) and check == len(pub_list) and check == len(lin_list):
					c_count = range(check)
					for c in c_count:
						title = ti_list[c]
						summary = sum_list[c]
						link = lin_list[c]
						published = pub_list[c]
						if published != "skip":
							published = clean_date(published)
						else:
							pass
						guid = link
						if published != "skip":
							anchor = moar_hash(link)
							df_source_raw.loc[df_source_raw.shape[0]] = [source, title, link, summary, published, guid, anchor]
						else:
							pass
				else:
					print("Mismatch in list counts.")

			except:
				print("USA Today borkage")
		elif ps == 'https://www.bbc.com/news/reality_check': #leaving this in in the hope that the BBC rebuilds their fact checking page
			source = "BBC News"
			try:
				main = soup.find('div', {'aria-labelledby' : 'latest-updates'})
				stories = main.find_all('article')
				for s in stories:
					#print(s)
					s_hold = ""
					holding = s.find('header')
					#print(holding)
					title = holding.find('h3').text
					#print(title)
					published = s.find('span', {'class' : 'qa-post-auto-meta'}).text
					published = clean_date(published)
					#print(f'Published: {published}')
					try:
						hold = holding.find('h3')
						link_tmp = hold.find('a')
						link = base_url + link_tmp['href']
					except:
						link = "skip"
					subset_sum = s.find('div', 'gs-u-mb+ gel-body-copy qa-post-body')
					ss = subset_sum.find_all('p')
					for s in ss:
						s_hold = s_hold + "\n" + s.text
					summary = s_hold.strip()
					if link != "skip":
						anchor = moar_hash(link)
						guid = link
						df_source_raw.loc[df_source_raw.shape[0]] = [source, title, link, summary, published, guid, anchor]
					else:
						pass
			except:
				print("BBC Borkage")
		else:
			print(f'No method specified for {ps}')
	except:
		print("Borkage")

driver.quit()

## Identify which posts have not been published

df_published_records = pd.read_csv(old_source, delimiter=',', quotechar='"',)
published_ids = df_published_records['anchor'].unique()
staged_ids = df_source_raw['anchor'].unique()

new_posts = list(set(staged_ids).difference(published_ids))
if publish_threshold > len(new_posts):
	sys.exit("No new posts! Nothing to publish!")
else:
	pass


## Stage new posts in df_source_filtered

for np in new_posts:
	df_new_one = df_source_raw[(df_source_raw['anchor'] == np)]
	source = df_new_one['source'].iloc[0]
	title = df_new_one['title'].iloc[0]
	link = df_new_one['link'].iloc[0]
	summary = df_new_one['summary'].iloc[0]
	published = df_new_one['published'].iloc[0]
	guid = df_new_one['guid'].iloc[0]
	anchor = df_new_one['anchor'].iloc[0]
	now = now_oclock
	df_source_filtered.loc[df_source_filtered.shape[0]] = [source, title, link, summary, published, guid, anchor, now]

## Generate report from df_source_filtered

df_source_filtered = df_source_filtered.sort_values(by='source', ascending=True)
df_source_filtered.to_csv(results_output, index = False)

sources = df_source_filtered['source'].unique()

excerpt = f"We have {len(new_posts)} new Fact Checks from {len(sources)} sources. Come read what's happening!"

report_list = "<ul>"
report_list_local = report_list
report_entries_all = "\n"

for s in sources:
	print(f'\n***\n{s}\n')
	source_anchor = clean_string(s)
	source_anchor = compress_text(source_anchor)
	report_list = report_list + f'<li><a href="{post_url}#{source_anchor}" alt="See updates from {s}">{s}</a></li>\n'
	report_list_local = report_list_local + f'<li><a href="#{source_anchor}" alt="See updates from {s}">{s}</a></li>\n'
	df_entries = df_source_filtered[(df_source_filtered['source'] == s)]
	df_entries = df_entries.sort_values(by='published', ascending=False)
	#print(df_entries.info())
	if use_accordion == "Y":
		report_entries_ind = f'<div class="lightweight-accordion" id="{source_anchor}"><details><summary class="lightweight-accordion-title"><span style="color: #eb3a09;">Fact checks from {s}</span></summary><div class="lightweight-accordion-body">'

	else:
		report_entries_ind = f'<h3 id="{source_anchor}">Fact checks from {s}</h3>'

	for p, q in df_entries.iterrows():
		title = q['title']
		published = q['published']
		link = q['link']
		summary = q['summary']
		anchor = q['anchor']
		report_entries_ind = report_entries_ind + f'\n<article id="{anchor}"><h4><a href="{link}" alt="Read {title} on {s}">{title}</a></h4>\n<p><b>Published <time datetime="{published}">{published}</time></b><br>{summary}</p><p>Read at <a href="{link}" alt="Read {title} on {s}">{s}</a></p></article>\n'

	if use_accordion == "Y":
		report_entries_ind = report_entries_ind + '</div></details></div>'
	else:
		pass
	report_entries_all = report_entries_all + report_entries_ind + "\n<hr>"

report_list = report_list + '</ul>' + '\n<p>This site is not affiliated with, or supported by, any of these sources. This site aggregates descriptions of fact checks, and links back to the original source. Read <a href="https://www.flammablepants.com/about/">About FlammablePants</a> for more information about this site.</p>\n'
report_list_local = report_list_local + '</ul>'

report_head = f'This report was run on {now_human}, and we have new fact checks from the following organizations:\n'

## Write report to external site

if create_local_report == "Y":
	report_local = report_head + report_list_local + report_entries_all
	write_file(output_name, report_local)

if create_remote_report == "Y":
	report = report_head + report_list + report_entries_all
	
	## Create blog post
	credentials = user + ':' + password
	token = base64.b64encode(credentials.encode())
	header = {'Authorization': 'Basic ' + token.decode('utf-8')}

	post = {
		'title':blog_title,
		'status': 'publish',
		'excerpt': excerpt,
		'content': report,
		'categories':'3',
		'author':'2'
		}

	response_post = requests.post(url_post, headers=header, json=post)
	if str(response_post) == "<Response [201]>":
		print(f"\n** The blog post titled '{blog_title}' was created.\n")
		combo = [df_published_records, df_source_filtered]
		df_published_records = pd.concat(combo)
		df_published_records.to_csv(old_source, index = False)
	else: 
		print(f"There seems to be an issue with creating the post. This was the response code:\n{response_post}")
else:
	pass
