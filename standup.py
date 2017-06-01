from errbot import BotPlugin, botcmd
import smtplib
from email.mime.text import MIMEText
import datetime

ALL_MEMBERS = 'members'
CURRENT_STANDUP = 'current_standup'

class Standup(BotPlugin):
    """
    This is a simple standup plugin that get the current status of the team and optionally send a reporting email.
    """

    def activate(self):
        super(Standup, self).activate()
        if ALL_MEMBERS not in self:
            self[ALL_MEMBERS] = []
        if CURRENT_STANDUP not in self:
            self[CURRENT_STANDUP] = {}
        self._started = False

    def deactivate(self):
        super(Standup, self).deactivate()

    def get_configuration_template(self):
        return {'smtp_from': 'me@example.com',
                'smtp_to': 'my_group@example.com',
                'smtp_login': 'me@example.com',
                'smtp_password': 'ascf123532',
                'smtp_server': 'smtp.gmail.com',
                'smtp_port': '587',
                'team_name': 'my team',
               }

    @property
    def members(self):
       if ALL_MEMBERS in self:
           return ','.join(self[ALL_MEMBERS])
       return None

    @botcmd
    def standup_start(self, msg, args):
        """Manually start the standup meeting in this room."""
        if not self.members:
            yield 'You need to add team members first'
            return

        if self._started:
            yield 'Hmm, this standup was already started, you can stop it with "!standup stop"'
            return

        self._started = True
        self[CURRENT_STANDUP] = {}
        yield 'Team %s, please %s standup !' % (self.config['team_name'], ' '.join(self[ALL_MEMBERS]))
        yield 'What did you do yesterday and what were your blockers ? Answer by mentioning me "%s I did blah ..."' % self.bot_identifier

    @botcmd
    def standup_stop(self, msg, args):
        """Manually stop the standup meeting in this room even if not all team members answered."""
        self._started = False
        return 'Thanks, I am archiving this standup.'

    @botcmd
    def standup_send(self, msg, args):
        """Send the summary email."""
        if not self.config:
            return 'This plugin is not configured.'

        server = smtplib.SMTP(self.config['smtp_server'], int(self.config['smtp_port']))
        server.ehlo()
        server.starttls()
        server.login(self.config['smtp_login'], self.config['smtp_password'])

        frm, to = self.config['smtp_from'], self.config['smtp_to']
        now = datetime.datetime.now()
        subject = 'Standup for %s [%s-%s-%s]' % (self.config['team_name'], now.year, now.month, now.day)
        body = subject + '\n\n' 
        for member, message in self[CURRENT_STANDUP].items():
            body += '- %s:\n"%s"\n\n\n' % (member, message)

        msg = MIMEText(body)
        msg['Subject']  = subject
        msg['From'] = frm
        msg['To'] = to
        server.sendmail(frm, [to], msg.as_string())
        server.quit()
        return "Message sent to %s." % to

    @botcmd
    def standup_last(self, msg, args):
        """Gives what was said at the last standup."""
        if not self[CURRENT_STANDUP]:
            yield 'I have no last standup recorded.'
            return
        for member, message in self[CURRENT_STANDUP].items():
            yield '*%s*:\n\n%s\n' % (member, message)

    def callback_mention(self, msg, mentioned_people):
        if self._started and not self._bot.is_from_self(msg) and self.bot_identifier in mentioned_people:
            if msg.frm != self.bot_identifier:  # the initial example.
                send_to = msg.frm.room if msg.is_group else msg.frm
                with self.mutable(CURRENT_STANDUP) as standups:
                    standups[str(msg.frm)] = msg.body.replace(str(self.bot_identifier), '')
                self.send(send_to, '%s, got it, thank you.' % msg.frm.nick)

    @botcmd
    def standup_add(self, msg, args):
        """Adds a new team member."""
        try:
            canonicalid = str(self.build_identifier(args))
        except Exception as e:
            return 'Could not build a valid chat identifier from %s: %s' % (args, e)
        with self.mutable(ALL_MEMBERS) as members:
            if canonicalid in members:
                return '%s is already a members.' % canonicalid
            members.append(canonicalid)
        return 'Done.\n\nAll members: %s.' % self.members

    @botcmd
    def standup_remove(self, msg, args):
        """Remove a team member."""
        try:
            canonicalid = str(self.build_identifier(args))
        except Exception as e:
            return 'Could not build a valid chat identifier from %s: %s' % (args, e)
        with self.mutable(ALL_MEMBERS) as members:
            if canonicalid not in members:
                return 'Cannot find %s in members.' % canonicalid
            members.remove(idd)
        return 'Done.\n\nAll members: %s.' % self.members

    @botcmd
    def standup_status(self, msg, args):
        """Status of the standup plugin."""
        return 'All members: %s.' % self.members

