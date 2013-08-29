# -*- coding: utf-8 -*-
# Time-stamp: <2013-08-29 20:44:27 vk>

import logging
import os
import werkzeug.utils  ## for sanitizing path components
import datetime
import re  ## RegEx: for parsing/sanitizing
#from lib.utils import *

## debugging:   for setting a breakpoint:  pdb.set_trace()
## NOTE: pdb hides private variables as well. Please use:   data = self._OrgParser__entry_data ; data['content']
import pdb
                #pdb.set_trace()## FIXXME


class HtmlizerException(Exception):
    """
    Exception for all kind of self-raised htmlizing errors
    """
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return repr(self.value)



class Htmlizer(object):
    """
    Class for generating HTML output of lazyblorg
    """

    logging = None  ## instance of logger

    template_definitions = None  ## list of lists ['description', 'content'] with content being the HTML templates
    targetdir = None  ## string of the base directory of the blog
    blog_data = None  ## internal representation of the complete blog content
    generate = None  ## list of IDs which blog entries should be generated
    increment_version = None  ## list of IDs which blog entries gets an update
    prefix_dir = None  ## string which is the base directory after targetdirectory

    ## this tag (withing tag list of article) determines if an article
    ## is a permanent blog page (tag is found) or a time-oriented
    ## (normal) blog-entry (this tag is missing).
    PERMANENT_ENTRY_TAG = 'permanent'

    ## this gets added to the time in order to describe time zone of the blog:
    TIME_ZONE_ADDON = '+02:00'

    ## find external links such as [[foo][bar]]:
    EXT_ORG_LINK_REGEX = re.compile('\[\[(.+?)\]\[(.+?)\]\]')

    ## find external links such as http(s)://foo.bar
    EXT_URL_LINK_REGEX = re.compile('([^"])(http(s)?:\/\/\S+)')

    ## find '&amp;' in an active URL and fix it to '&':
    FIX_AMPERSAND_URL_REGEX = re.compile('(href="http(s)?://\S+?)&amp;(\S+?")')

    BLOG_PREFIX = u'blog'  ## FIXXME: this is defined in lazyblorg.py -> so do replace by parameter of this class!

    def __init__(self, template_definitions, prefix_dir, targetdir, blog_data, generate, increment_version):
        """
        This function FIXXME

        @param template_definitions: list of lists ['description', 'content'] with content being the HTML templates
        @param prefix: string which is the base directory after targetdirectory
        @param targetdir: string of the base directory of the blog
        @param blog_data: internal representation of the complete blog content
        @param generate: list of IDs which blog entries should be generated
        @param increment_version: list of IDs which blog entries gets an update
        """

        ## initialize class variables
        self.template_definitions = template_definitions
        self.prefix_dir = prefix_dir
        self.targetdir = targetdir
        self.blog_data = blog_data
        self.generate = generate
        self.increment_version = increment_version

         ## create logger (see http://docs.python.org/2/howto/logging-cookbook.html)
        self.logging = logging.getLogger('lazyblorg.htmlizer')

        self.logging.debug("Htmlizer initiated with %s templ.def., %s blog_data, %s generate, %s increment" %
                           (str(len(template_definitions)), str(len(blog_data)), str(len(generate)),
                            str(len(increment_version))))

    def run(self):
        """
        Basic method that creates all the output.

        @param FIXXME
        @param return: FIXXME
        """

        ## FIXXME: copy CSS file (future enhancement - for now it shall be manually placed)

        for entry in self.blog_data:

            ## example entry:
            ## {'level': 2,
            ## 'timestamp': datetime.datetime(2013, 2, 14, 19, 2),
            ## 'tags': [u'blog', u'mytest', u'programming'],
            ## 'created': datetime.datetime(2013, 2, 12, 10, 58),
            ## 'finished-timestamp-history': [datetime.datetime(2013, 2, 14, 19, 2)],
            ## 'title': u'This is an example blog entry',
            ## 'id': u'2013-02-12-lazyblorg-example-entry',
            ## 'content': [['par', u'foo...'], [...]]
            ##  }

            entry = self.sanitize_blog_content(entry)

            if self.PERMANENT_ENTRY_TAG in entry['tags']:
                self.logging.debug("entry \"%s\" is a permanent page (not time-oriented)" % entry['id'])
                pass  ## FIXXME

            else:
                self.logging.debug("entry \"%s\" is an ordinary time-oriented blog entry" % entry['id'])
                self._create_time_oriented_blog_article(entry)

    def sanitize_blog_content(self, entry):
        """
        Inspects a selection of the entry data and sanitizes it for HTML.

        Currently things that get sanitized:
        - [[foo][bar]] -> <a href="foo">bar</a>
        - id:foo -> internal links to blog article if "foo" is found as an id
        - [[id:foo]] -> see id:foo above

        @param entry: blog entry data
        @param return: partially sanitized entry
        """

        for element in entry['content']:

            #pdb.set_trace()## FIXXME

            if element[0] == 'par':

                ## join all lines of a paragraph to one single long
                ## line in order to enable sanitizing URLs and such:
                content = ' '.join(element[1:])

                content = self.sanitize_html_characters(content)
                content = self.sanitize_external_links(content)
                content = self.fix_ampersands_in_url(content)

            elif element[0] == 'heading':
                title = element[1]['title']
                title = self.sanitize_html_characters(title)
                title = self.sanitize_external_links(title)
                title = self.fix_ampersands_in_url(title)
                element[1]['title'] = title

            elif element[0] == 'list-itemize':
                for listitem in element[1]:
                    content = self.sanitize_html_characters(listitem)
                    content = self.sanitize_external_links(content)
                    content = self.fix_ampersands_in_url(content)
                    element[1][listitem] = content

            elif element[0] == 'html-block' or element[0] == 'verse-block':
                pass
            else:
                message = "htmlizer.py/sanitize_blog_string(): content element [" + str(element[0]) + "] not recognized."
                self.logging.critical(message)
                raise HtmlizerException(message)

        return entry

    def fix_ampersands_in_url(self, content):
        """
        sanitize_html_characters() is really dumb and replaces
        ampersands in URLs as well. This method finds those broken
        URLs and fixes them.

        If this method of fixing something that should be done in a
        correct way in the first place smells funny, you are
        right. However, this seemed to be the more efficient way
        regarding to implementation. Fix it, if you like :-)

        FIXXME: Does not replace several ampersands in the very same
        URL. However, this use-case of several ampersands in one URL
        is very rare.

        @param entry: string
        @param return: fixed string
        """

        result = re.sub(self.FIX_AMPERSAND_URL_REGEX, r'\1&\3', content)
        if result != content:
            self.logging.debug("fix_ampersands_in_url: fixed \"%s\" to \"%s\"" % (content, result))

        return result

    def sanitize_html_characters(self, content):
        """
        Replaces all occurrences of [<>] with their HTML representation.

        @param entry: string
        @param return: sanitized string
        """

        return content.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

    def sanitize_external_links(self, content):
        """
        Replaces all external Org-mode links of type [[foo][bar]] with
        <a href="foo">bar</a>.

        Additionally, directly written URLs are transformed in a-hrefs
        as well.

        @param entry: string
        @param return: sanitized string
        """

        orglink_result = re.sub(self.EXT_ORG_LINK_REGEX, r'<a href="\1">\2</a>', content)
        #if orglink_result != content:
        #    self.logging.debug("sanitize_external_links: changed \"%s\" to \"%s\"" % (content, orglink_result))

        urllink_result = re.sub(self.EXT_URL_LINK_REGEX, r'\1<a href="\2">\2</a>', orglink_result)
        #if urllink_result != orglink_result:
        #    self.logging.debug("sanitize_external_links: changed \"%s\" to \"%s\"" %
        #                       (orglink_result, urllink_result))

        return urllink_result


    def _create_time_oriented_blog_article(self, entry):
        """
        Creates a (normal) time-oriented blog article (in contrast to a permanent blog article).

        @param entry: blog entry data
        @param return: FIXXME
        """

        path = self._create_target_path_for_id(entry['id'])

        filename = os.path.join(path, "index.html")

        with open(filename, 'wb') as output:

            ## replace-loop of all relevant strings and placeholder-strings
            ## article-header       | TITLE, ABOUT-BLOG, BLOGNAME, ARTICLE-(YEAR,MONTH,DAY,PUB*) |
            ## article-header-begin | TITLE, ABOUT-BLOG, BLOGNAME, ARTICLE-(YEAR,MONTH,DAY,PUB*) |
            ## article-tags-begin   | TITLE, ABOUT-BLOG, BLOGNAME, ARTICLE-(YEAR,MONTH,DAY,PUB*) |
            ## article-tag          | TAGNAME                                                    |
            ## article-tags-end     | TITLE, ABOUT-BLOG, BLOGNAME, ARTICLE-(YEAR,MONTH,DAY,PUB*) |
            ## article-header-end   | TITLE, ABOUT-BLOG, BLOGNAME, ARTICLE-(YEAR,MONTH,DAY,PUB*) |
            ## content              | *                                                          |
            ## article-end          | TITLE, ABOUT-BLOG, BLOGNAME, ARTICLE-(YEAR,MONTH,DAY,PUB*) |
            ## article-footer       | TITLE, ABOUT-BLOG, BLOGNAME, ARTICLE-(YEAR,MONTH,DAY,PUB*) |

            content = u''

            for articlepart in ['article-header', 'article-header-begin', 'article-tags-begin']:
                content += self.template_definition_by_name(articlepart)
            output.write(self._replace_general_article_placeholders(entry, content))
            
            #pdb.set_trace()## FIXXME
            content = self._replace_tag_placeholders(entry['tags'], self.template_definition_by_name('article-tag'))
            output.write(content)

            content = u''
            for articlepart in ['article-tags-end', 'article-header-end']:
                content += self.template_definition_by_name(articlepart)
            output.write(self._replace_general_article_placeholders(entry, content))
            
            #FIXXME: output.write(self._generate_main_content(entry))

            content = u''
            for articlepart in ['article-end', 'article-footer']:
                content += self.template_definition_by_name(articlepart)
            output.write(self._replace_general_article_placeholders(entry, content))

        return

    def _generate_main_content(self, entry):
        """
        Uses the blog_data content of entry and returns a string with
        the htmlized blog article content.

        @param entry: blog data content
        @param return: string with replaced placeholders of the body of the article
        """
        
        pass ## FIXXME

    def _replace_tag_placeholders(self, tags, template_string):
        """
        Takes the list of tags and the template definition for tags
        and returns their concatenated string.

        The tag "blog" will be suppressed.

        @param tags: list of strings containing all tags of an entry
        @param template_string: string with placeholders instead of tag
        @param return: string with replaced placeholders
        """

        assert(type(tags) == list)
        assert(template_string)

        result = u''

        for tag in tags:
            if tag == self.BLOG_PREFIX:
                continue
            else:
                result += template_string.replace('#TAGNAME#', tag)

        return result

    def _replace_general_article_placeholders(self, entry, template):
        """
        General article placeholders are:
        - #TITLE#
    - #ABOUT-BLOG#
    - #BLOGNAME#
        - #ARTICLE-YEAR#: four digit year of the article (folder path)
        - #ARTICLE-MONTH#: two digit month of the article (folder path) 
        - #ARTICLE-DAY#: two digit day of the article (folder path)
        - #ARTICLE-PUBLISHED-HTML-DATETIME#: time-stamp of publishing in HTML
          date-time format
        - #ARTICLE-PUBLISHED-HUMAN-READABLE#: time-stamp of publishing in

        This method replaces all placeholders from above with their
        blog article content.

        @param entry: blog entry data
        @param template: string with placeholders instead of content data
        @param return: template with replaced placeholders
        """

        #pdb.set_trace()## FIXXME

        content = template
        
        content = content.replace('#TITLE#', entry['title'])
        content = content.replace('#ABOUT-BLOG#', 'FIXXME:about-blog')
        content = content.replace('#BLOGNAME#', 'FIXXME:blogname')

        oldesttimestamp, year, month, day, hours, minutes = self._get_oldest_timestamp_for_entry(entry)
        iso_timestamp = '-'.join([year, month, day]) + 'T' + hours + ':' + minutes
        
        content = content.replace('#ARTICLE-YEAR#', year)
        content = content.replace('#ARTICLE-MONTH#', month)
        content = content.replace('#ARTICLE-DAY#', day)
        content = content.replace('#ARTICLE-PUBLISHED-HTML-DATETIME#', iso_timestamp + self.TIME_ZONE_ADDON)
        content = content.replace('#ARTICLE-PUBLISHED-HUMAN-READABLE#', iso_timestamp)

        return content

    def _target_path_for_id(self, entryid):
        """
        Creates a directory path for a given blog ID such as:
        "TARGETDIR/blog/2013/02/12/ID" from the oldest finished
        time-stamp.

        @param entryid: ID of a blog entry
        @param return: FIXXME
        """

        entry = self.blog_data_with_id(entryid)

        oldesttimestamp, year, month, day, hours, minutes = self._get_oldest_timestamp_for_entry(entry)

        folder = werkzeug.utils.secure_filename(entryid)

        if folder[0:11] == year + '-' + month + '-' + day + '-':
            ## folder contains the date-stamp in ISO format -> get rid of it (it's in the path anyway)
            folder = folder[11:]

        return os.path.join(self.targetdir, self.prefix_dir, year, month, day, folder)

    def _get_oldest_timestamp_for_entry(self, entry):
        """
        Reads data of entry and returns datetime object of the oldest
        time-stamp of the finished-timestamp-history.

        Example result: datetime.datetime(2013, 8, 29, 19, 40)

        Implicit assumptions:
        - no blog article is from the future (comparison to now)

        @param entry: data of a blog entry
        @param return: datetime object of its oldest time-stamp within finished-timestamp-history
        @param return: year: four digit year as string
        @param return: month: two digit month as string
        @param return: day: two digit day as string
        @param return: hours: two digit hours as string
        @param return: minutes: two digit minutes as string
        """

        assert(entry)
        assert('finished-timestamp-history' in entry.keys())

        oldesttimestamp = datetime.datetime.now()
        for timestamp in entry['finished-timestamp-history']:
            if timestamp < oldesttimestamp:
                oldesttimestamp = timestamp

        return oldesttimestamp, str(oldesttimestamp.year).zfill(2), str(oldesttimestamp.month).zfill(2), \
            str(oldesttimestamp.day).zfill(2), \
            str(oldesttimestamp.hour).zfill(2), str(oldesttimestamp.minute).zfill(2)


    def _create_target_path_for_id(self, entryid):
        """
        Creates a folder hierarchy for a given blog ID such as: TARGETDIR/blog/2013/02/12/ID

        @param entryid: ID of a blog entry
        @param return: path that was created
        """

        self.logging.debug("_create_target_path_for_id(%s) called" % entryid)

        assert(os.path.isdir(self.targetdir))
        idpath = self._target_path_for_id(entryid)

        try:
            self.logging.debug("creating path: \"%s\"" % idpath)
            os.makedirs(idpath)
        except OSError:
            ## thrown, if it exists (no problem) or can not be created -> check!
            if os.path.isdir(idpath):
                self.logging.debug("path [%s] already existed" % idpath)
            else:
                message = "path [" + idpath + "] could not be created. Please check and fix before next run."
                self.logging.critical(message)
                raise HtmlizerException(message)

        return idpath

    def template_definition_by_name(self, name):
        """
        Returns the template definition whose name matches "name".

        Implicit assumptions:
        - template_definitions is a list of list of exactly three elements
        - this does not check if "name" is a valid/existing template definition string

        @param entryid: name of a template definition
        @param return: content of the template definition
        """

        ## examples:
        ## self.template_definitions[0][1] -> u'article-header'
        ## self.template_definitions[0][2] -> [u'  <!DOCTYPE html>', u'  <html xmlns="http...']
        #pdb.set_trace()## FIXXME
        return '\n'.join([x[2:][0] for x in self.template_definitions if x[1] == name][0])

    def blog_data_with_id(self, entryid):
        """
        Returns the blog_data entry whose id matches entryid.

        @param entryid: ID of a blog entry
        @param return: blog_data element
        """

        matching_elements = [x for x in self.blog_data if entryid == x['id']]

        if len(matching_elements) == 1:
            return matching_elements[0]
        else:
            message = "blog_data_with_id(\"" + entryid + \
                "\") did not find exactly one result (as expected): [" + str(matching_elements) + "]"
            self.logging.error(message)
            raise HtmlizerException(message)  ## FIXXME: maybe an Exception is too harsh here? (error-recovery?)


#    def __filter_org_entry_for_blog_entries(self):
#        """
#        Return True if current entry from "self.__entry_data" is a valid and
#        complete blog article and thus can be added to the blog data.
#
#        @param return: True if OK or False if not OK (and entry has to be skipped)
#        """



# Local Variables:
# mode: flyspell
# eval: (ispell-change-dictionary "en_US")
# End: