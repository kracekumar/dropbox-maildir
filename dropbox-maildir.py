# -*- coding: utf-8 -*-

import logging
import sys
import os
import maildir
import dropbox


DIRS = ['new', 'cur', 'attachments', 'tmp']


class Dropbox(object):
    def __init__(self, access_token, path, app_key, app_secret, email):
        self.service = "dropbox"
        self.access_token, self.path = access_token, path
        self.app_key, self.app_secret = app_key, app_secret
        self.client = dropbox.client.DropboxClient(self.access_token)
        self.email = email
        self.email.create_db()
        self.tmp_dir = '/tmp' #FIXME: Only Linux
        self.set_logger()
        self.email.create_directories(self.tmp_dir, dirs=DIRS)

    def set_logger(self):
        self.logger_name = "dropbox_backup"
        self.logger = logging.getLogger(self.logger_name)
        self.logger.setLevel(logging.DEBUG)
        self.fh = logging.FileHandler('dropbox_backup.log')
        self.fh.setLevel(logging.INFO)
        frmt = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        self.fh.setFormatter(frmt)
        self.logger.addHandler(self.fh)
        self.change_email_settings()

    def change_email_settings(self):
        self.email.db = "dropbox_backup.db"
        self.email.logger = self.logger
        self.email.fh = self.fh
        self.email.create_db()

    def create_folder(self, path=None):
        try:
            path = path or self.path
            self.client.file_create_folder(path)
            self.logger.info("Folder created %s" % path)
        except dropbox.rest.ErrorResponse, e:
            if not e.status == 403:
                print(e.body)
        finally:
            self.dropbox_new = self.path + "/" + "new"
            self.dropbox_tmp = self.path + "/" + "tmp"
            self.dropbox_attachment = self.path + "/" + "attachments"

    def run_forever(self):
        for directory in DIRS:
            self.create_folder(self.path + '/' + directory)
        if not self.email.mail.state == maildir.mail.IMAP4_MESSAGE.SELECTED:
            self.email.connect()
            # Get all mailboxes
            self.email.fetch_lists()
            # Get All mailboxes
            for m in self.email.mailboxes:
                self.email.select_mailbox(m)
                r = self.email.fetch_details()
                if r:
                    #Get Message ids
                    ids = r[1][0].split()
                    for mail_id in ids:
                        msg = self.email.fetch(mail_id[:100])
                        #Store Email body
                        if msg:
                            path = self.tmp_dir + os.path.sep + self.email.username
                            self.email.save_to_disk(msg, path=path)
                            base = path + os.path.sep + 'new'
                            #Copy do dropbox and delete local link
                            for f in os.listdir(base):
                                fp = open(base + os.path.sep + f, 'rb')
                                db_path = self.dropbox_new + '/' + fp.name.split('/')[-1]
                                resp = self.client.put_file(db_path, fp)
                                self.logger.info("file uploaded to drop path %s" %(resp['path']))
                                fp.close()
                                os.remove(base + os.path.sep + fp.name.split('/')[-1])

                        #Store Attachments
                            if self.email.has_attachment(msg):
                                attachments = self.email.get_attachment(msg)
                                for item in attachments:
                                    self.email.store_attachment(item, attachments[item], path=path)
                                base = path + os.path.sep + 'attachments'
                            #Copy do dropbox and delete local link
                                for f in os.listdir(base):
                                    fp = open(base + os.path.sep + f, 'rb')
                                    db_path = self.dropbox_attachment + '/' + fp.name.split('/')[-1]
                                    resp = self.client.put_file(db_path, fp)
                                    self.logger.info("file uploaded to drop path %s" % (resp['path']))
                                    fp.close()
                                    os.remove(base + os.path.sep + fp.name.split('/')[-1])
            #sleep(60)
            try:
                self.email.mail.close()
            except:
                pass
            self.email.mail.logout()


def main():
    if len(sys.argv) <= 2:
        filepath = sys.argv[1]
        try:
            config = maildir.cli.read_config_file(filepath)
            if maildir.cli.valid_config(config):
                for c in config.config:
                    if 'access_token' in c and 'app_key' in c and 'app_secret' in c:
                        email = maildir.mail.SSLEmail(config=c)
                        d = Dropbox(access_token=c['access_token'].strip(), path=c['path'], app_key=c['app_key'], app_secret=c['app_secret'], email=email)
                        d.run_forever()
                    else:
                        print("access_token, app_key, app_secret are required for dropbox")
        except Exception, e:
            raise
            raise Exception(e)
    else:
        print("python dropbox-maildir config-file-fullpath.py")

if __name__ == "__main__":
    main()
