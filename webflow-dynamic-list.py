import sys
import os
import urllib
import glob
import re
import urlparse
from shutil import copyfile
from lxml import html
from lxml import etree

if len(sys.argv) < 2:
  print 'Pass in the URL to your remote site and try again! For example:'
  print '  python webflow-dynamic-list.py http://mysite.webflow.io'
  sys.exit()

remoteSiteUrl = sys.argv[1] 
localImagesDirectory = 'images/' 
backgroundImagePattern = "background-image:\s*url\(\'(.*)\'\)"

# Ensure images directory exists
if not os.path.exists(localImagesDirectory):
    os.makedirs(localImagesDirectory)

# Determine dynamic collections from detail pages
def getCollectionName(filename):
  reg = re.match('detail_(.*).html', filename)
  return re.match('detail_(.*).html', filename).groups()[0]

dynamicCollectionNames = map(getCollectionName, glob.glob('detail_*.html'))

print 'Found ' + str(len(dynamicCollectionNames)) + ' dynamic collections: ' + ",".join(dynamicCollectionNames)

def downloadImage(remoteUrl, localUrl):
  if remoteUrl.startswith('http') and not os.path.isfile(localUrl):
    print ' - Downloading image: ' + remoteUrl
    urllib.urlretrieve(remoteUrl, localUrl)

def processImageTag(node):
  # Need to change this image's source to point to the local file we will download
  src = node.attrib['src']
  newImgSrc = urlparse.urljoin(localImagesDirectory, urllib.unquote(src.split('/')[-1]))
  node.attrib['src'] = newImgSrc
  downloadImage(src, newImgSrc)

def processImageBackground(node):
  if 'style' not in node.attrib:
    return

  style = node.attrib['style']
  reg = re.match(backgroundImagePattern, style)
  if reg == None:
    return

  src = reg.groups()[0]
  newImgSrc = urlparse.urljoin(localImagesDirectory, urllib.unquote(src.split('/')[-1]))
  node.attrib['style'] = re.sub(backgroundImagePattern, "background-image: url('" + newImgSrc + "')", node.attrib['style'])

  downloadImage(src, newImgSrc)

def processDynamicPage(node):
  # Ensure this node has a link that we are going to process
  if 'href' not in node.attrib:
    return

  # Ensure the link is to a dynamic page
  link = node.attrib['href']
  collectionName = None
  for name in dynamicCollectionNames:
    if link.startswith('/' + name + '/'):
      collectionName = name
      break

  if collectionName == None:
    return

  # Process the link -- remove leading forward slash, and replace slashes in the link with hyphens
  #   because everything in the exported code from Webflow assumes things are in the same directory
  newLink = link[1:].replace('/', '-') + '.html' # remove leading forward slash
  node.attrib['href'] = newLink

  if not os.path.isfile(newLink):
    print ' - creating dynamic page: ' + link
    copyfile('detail_' + collectionName + '.html', newLink)
    replaceDynamicListsInFile(newLink, 'exported-dynamic-content', link)

def replaceDynamicList(dynLists):
  # Download images inside of the remote dynamic list
  localDynamicList = dynLists[0]
  remoteDynamicList = dynLists[1]

  map(processImageTag, remoteDynamicList.findall('.//img'))
  map(processImageBackground, remoteDynamicList.xpath('.//*'))
  map(processDynamicPage, remoteDynamicList.xpath('.//*'))

  localDynamicList.getparent().replace(localDynamicList, remoteDynamicList)  

def replaceDynamicListsInFile(htmlFile, dynamicClass, computedRemoteUrl):
  print htmlFile

  # Ignore detail files
  if htmlFile.startswith('detail_'):
    print ' - skipping (dynamic list detail file)'
    return 

  # Read local file to see if there is any dynamic content
  with open(htmlFile, 'r+') as localFile:
    localHtml = html.fromstring(localFile.read())
    localDynamicLists = localHtml.find_class(dynamicClass)
    if len(localDynamicLists) == 0:
      print ' - no dynamic lists were found'
      return

    remoteRelativeUrl = computedRemoteUrl if computedRemoteUrl != None else htmlFile[0:-5] if htmlFile != 'index.html' else ''
    remotePageUrl = urlparse.urljoin(remoteSiteUrl, remoteRelativeUrl)
    remoteHtml = html.fromstring(urllib.urlopen(remotePageUrl).read())
    remoteDynamicLists = remoteHtml.find_class(dynamicClass)
    if len(remoteDynamicLists) != len(localDynamicLists):
      print ' - error: number of dynamic lists does not match up with the remote version at: ' + remotePageUrl
      return

    map(replaceDynamicList, zip(localDynamicLists, remoteDynamicLists))

    # Save file with dynamic content modifications
    localFile.seek(0)
    localFile.write(etree.tostring(localHtml,
       encoding="utf-8", method="html", xml_declaration=None,
       pretty_print=True, with_tail=True, standalone=None,
       doctype='<!DOCTYPE html>'))
    localFile.truncate()
    localFile.close()

    print ' - ' + str(len(remoteDynamicLists)) + ' dynamic list(s) processed'

for globFile in glob.glob('*.html'):
  replaceDynamicListsInFile(globFile, 'w-dyn-list', None)

print 'Done processing dynamic data!'
