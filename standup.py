from errbot import BotPlugin, botcmd
import smtplib
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
                'smtp_server': 'smtp.gmail.com:587',
               }

    @property
    def members(self):
       if ALL_MEMBERS in self:
           return ','.join(str(m) for m in self[ALL_MEMBERS])
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
        yield 'Please %s standup !' % ' '.join(str(m) for m in self[ALL_MEMBERS])
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

        server = smtplib.SMTP(self.config['smtp_server'])
        server.ehlo()
        server.starttls()
        server.login(self.config['smtp_server'], self.config['smtp_password'])

        now = datetime.datetime.now()
        body = 'Standup for %s-%s-%s\n\n' % (now.year, now.month, now.day)
        for member, message in self[CURRENT_STANDUP]:
            body += '*%s*:\n%s\n\n' % (member, message)
        server.sendmail(self.config['smtp_from'], self.config['smtp_to'], body)
        server.quit()

    @botcmd
    def standup_last(self, msg, args):
        """Gives what was said at the last standup."""
        if not self[CURRENT_STANDUP]:
            yield 'I have no last standup recorded.'
            return
        for member, message in self[CURRENT_STANDUP]:
            yield '*%s*:\n\n%s\n' % (member, message)

    def callback_mention(self, message, mentioned_people):
        if self._started and self.bot_identifier in mentioned_people:
            if message.frm != self.bot_identifier:  # the initial example.
                send_to = message.frm.room if message.is_group else message.frm
                with self.mutable(CURRENT_STANDUP) as standups:
                    standups[message.frm] = message.body.replace(str(self.bot_identifier), '')
                self.send(send_to, 'Noted %s, thank you.' % message.frm)

    @botcmd
    def standup_add(self, msg, args):
        """Adds a new team member."""
        try:
            idd = self.build_identifier(args)
        except Exception as e:
            return 'Could not build a valid chat identifier from %s: %s' % (args, e)
        with self.mutable(ALL_MEMBERS) as members:
            if idd in members:
                return '%s is already a members.' % str(idd)
            members.append(idd)
        return 'Done.\n\nAll members: %s.' % self.members

    @botcmd
    def standup_remove(self, msg, args):
        """Remove a team member."""
        try:
            idd = self.build_identifier(args)
        except Exception as e:
            return 'Could not build a valid chat identifier from %s: %s' % (args, e)
        with self.mutable(ALL_MEMBERS) as members:
            if idd not in members:
                return 'Cannot find %s in members.' % str(idd)
            members.remove(idd)

        return 'Done.\n\nAll members: %s.' % self.members

    @botcmd
    def standup_status(self, msg, args):
        """Status of the standup plugin."""

        return 'All members: %s.' % self.members

