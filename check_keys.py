import feedparser
from collections import Counter

feed_source = ['https://www.politifact.com/rss/all/', 'https://www.factcheck.org/feed/', 'https://leadstories.com/atom.xml', 'https://www.snopes.com/feed']


feedcount = 0
m_list = []
e_list = []
for fs in feed_source:
	feedcount += 1
	try:
		print("\n* * *")
		print(f'parsing {fs}')
		feed = feedparser.parse(fs)
		meta = feed.keys()
		for m in meta:
			m_list.append(m)
		print(f"Feed meta: {meta}")
		source = feed['feed']['title']
		print(source)
		print(f"total entries: {len(feed['entries'])}")
		if len(feed['entries']) > 0:
			ent_list = feed['entries'][0].keys()
			for e in ent_list:
				e_list.append(e)
			print(ent_list)
	except:
		print(f'Error parsing {fs}')
print(f'\n- - - - - - - - -\nTotal feeds analysed: {feedcount}\n')
print("All meta keys:\n")
print(Counter(m_list))
print("\nAll keys in entries:\n")
print(Counter(e_list))

