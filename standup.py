from collections import namedtuple
import datetime
import smtplib
from email.mime.text import MIMEText

from errbot import BotPlugin, botcmd, arg_botcmd
from errbot.backends.base import Room

TEAMS = 'teams'
STANDUPS = 'standups'

Team = namedtuple('Team', ['name', 'room', 'email', 'members'])

class Standup(BotPlugin):
    """
    This is a simple standup plugin that get the current status of the team and optionally send a reporting email.
    """
    def find_team_by_name(self, name):
        for t in self[TEAMS]:
            if t.name == name:
                return t
        return None

    def find_team_by_room(self, room):
        room = str(room)
        for t in self[TEAMS]:
            if t.room == room:
                return t
        return None

    def find_team_from_msg_or_name(self, msg, name=None):
        try:
            if name:
                return self.find_team_by_name(name), None
            if msg.is_group:
                return self.find_team_by_room(msg.frm.room), None
        except ValueError as v:
            return None, str(v)
        return None, 'Either you need to execute the command in a room or pass it a team name as parameter'

    def add_team(self, team):
        if self.find_team_by_name(team.name) is not None:
            raise ValueError(f'A team with the name {team.name} already exist')
        if self.find_team_by_room(team.room) is not None:
            raise ValueError(f'A team in the channel {team.channel} already exist')
        with self.mutable(TEAMS) as teams:
            teams.append(team)

    def activate(self):
        super(Standup, self).activate()
        if TEAMS not in self:
            self[TEAMS] = []
        if STANDUPS not in self:
            self[STANDUPS] = {}

    def deactivate(self):
        super(Standup, self).deactivate()

    def get_configuration_template(self):
        return {'smtp_from': 'me@example.com',
                'smtp_login': 'me@example.com',
                'smtp_password': 'ascf123532',
                'smtp_server': 'smtp.gmail.com',
                'smtp_port': '587',
               }

    @arg_botcmd('email', type=str)
    @arg_botcmd('room', type=str)
    @arg_botcmd('name', type=str)
    def standup_teams_add(self, msg, name, room, email):
        """Creates a team. You need to specify in which channel the team usually is."""
        # Slack gobbles the #
        if self.mode == 'slack' and room[0] != '#':
            room = '#' + room

        try:
            r = self.build_identifier(room)
            assert isinstance(r, Room)
        except Exception as e:
            return f'Could not build a valid room from {room}: {e}'

        team = Team(name=name, room=room, email=email, members=[])
        try:
            self.add_team(team)
        except ValueError as v:
            return str(v)
        return 'Team added.'

    @arg_botcmd('name', type=str)
    def standup_teams_remove(self, msg, name):
        """Delete a team."""
        team = self.find_team_by_name(name)

        if not team:
            return f'Cannot find the team {name}'

        with self.mutable(TEAMS) as teams:
            teams.remove(team)
        return 'Team removed.'

    @botcmd
    def standup_teams(self, msg, _):
        """List the current teams."""
        if not self[TEAMS]:
            yield 'No team.'
            return

        for team in self[TEAMS]:
            yield team


    @arg_botcmd('member', type=str)
    @arg_botcmd('team_name', type=str)
    def standup_members_add(self, msg, team_name, member):
        """Adds a new team member."""
        try:
            canonicalid = str(self.build_identifier(member))
        except Exception as e:
            return f'Could not build a valid chat identifier from {member}: {e}'
        with self.mutable(TEAMS) as teams:
            for team in teams:
                if team.name == team_name:
                    break
            else:
                return f'Cannot find the team {team_name}.'

            if canonicalid in team.members:
                return f'{canonicalid} is already a members.'

            team.members.append(canonicalid)
        return f'Done.\n\nAll members for {team_name}: {", ".join(team.members)}.'

    @arg_botcmd('member', type=str)
    @arg_botcmd('team_name', type=str)
    def standup_members_remove(self, msg, team_name, member):
        """Remove a team member."""
        """Adds a new team member."""
        try:
            canonicalid = str(self.build_identifier(member))
        except Exception as e:
            return f'Could not build a valid chat identifier from {member}: {e}'

        with self.mutable(TEAMS) as teams:
            for team in teams:
                if team.name == team_name:
                    break
            else:
                return f'Cannot find the team {team_name}.'

            if canonicalid not in team.members:
                return f'{canonicalid} is not a member of {team_name}.'

            team.members.remove(canonicalid)
            return f'Done.\n\nAll remaining members for {team_name}: {", ".join(team.members)}.'

    @arg_botcmd('team_name', type=str, nargs='?')
    def standup_start(self, msg, team_name=None):
        """Manually start the standup meeting in this room."""
        team, err = self.find_team_from_msg_or_name(msg, team_name)
        if not team:
            return err

        if not team.members:
            return 'You need to add team members first'

        if team.name in self[STANDUPS]:
            return 'Hmm, this standup was already started, you can stop it with "!standup end"'

        with self.mutable(STANDUPS) as standups:
            standups[team.name] = {}

        blurb = f'Team {team.name}, please {" ".join(team.members)} standup !\n\n \
What did you do yesterday and what were your blockers ? \n\n\
Answer by mentioning me "{self.bot_identifier} I did something something ..."'

        self.send(identifier=self.build_identifier(team.room),
                  text=blurb,
                  in_reply_to=msg)

    @arg_botcmd('team_name', type=str, nargs='?')
    def standup_end(self, msg, team_name=None):
        """Ends the standup and send the summary email."""
        if not self.config:
            return 'This plugin is not configured.'

        team, err = self.find_team_from_msg_or_name(msg, team_name)
        if not team:
            return err

        server = smtplib.SMTP(self.config['smtp_server'], int(self.config['smtp_port']))
        server.ehlo()
        server.starttls()
        server.login(self.config['smtp_login'], self.config['smtp_password'])

        frm, to = self.config['smtp_from'], team.email
        now = datetime.datetime.now()
        subject = f'Standup for {team.name} [{now.year}-{now.month}-{now.day}]'
        body = subject + '\n\n'
        for member, message in self[STANDUPS][team.name].items():
            body += f'- {member}:\n"{message}"\n\n\n'

        msg = MIMEText(body)
        msg['Subject']  = subject
        msg['From'] = frm
        msg['To'] = to
        server.sendmail(frm, [to], msg.as_string())
        server.quit()

        with self.mutable(STANDUPS) as su:
            del su[team.name]

        return f'Message sent to {to}.'

    @arg_botcmd('team_name', type=str, nargs='?')
    def standup_status(self, msg, team_name = None):
        """Gives the current state of the standup."""
        team, err = self.find_team_from_msg_or_name(msg, team_name)
        if not team:
            yield err
            return

        if team.name not in self[STANDUPS]:
            yield f'I have no active standup for {team.name}.'
            return

        member_messages = self[STANDUPS][team.name].items()

        if not member_messages:
            yield 'The standup has started but nobody has reported anything yet.'
            return

        yield '## All the current messages'
        for member, message in member_messages:
            yield f'*{member}*:\n\n{message}\n'
        left = set(team.members) - set(self[STANDUPS][team.name])
        if left:
            yield f'I am still waiting on {", ".join(left)}'
        else:
            yield f'Everybody had reported, you are ready to !standup end'

    @arg_botcmd('team_name', type=str, nargs='?')
    def standup_cancel(self, msg, team_name=None):
        team, err = self.find_team_from_msg_or_name(msg, team_name)
        if not team:
            return err

        if team.name not in self[STANDUPS]:
            return f'I have no active standup for {team.name}.'

        with self.mutable(STANDUPS) as su:
            del su[team.name]

        return f'Standup for {team.name} cancelled'

    @arg_botcmd('message', type=str)
    @arg_botcmd('member', type=str)
    @arg_botcmd('team_name', type=str)
    def standup_cover(self, msg, team_name, member, message):
        """Cover for a teammate and report for him."""

        team = self.find_team_by_name(team_name)

        if not team:
            return f'Cannot find the team {team_name}.'

        if team.name not in self[STANDUPS]:
            return f'There is no active standup for {team.name}.'

        with self.mutable(STANDUPS) as standups:
            standups[team.name][member] = message

        return f'Message recorded for {member}.'

    def callback_mention(self, msg, mentioned_people):
        if self._bot.is_from_self(msg) or msg.frm == self.bot_identifier:
            return

        if self.bot_identifier not in mentioned_people:
            return

        send_to = msg.frm.room if msg.is_group else msg.frm
        team, err = self.find_team_from_msg_or_name(msg, None)

        if not team or team.name not in self[STANDUPS]:
            # simply no team associated with this room or no standup
            return
        person = msg.frm.person if msg.is_group else str(msg.frm)
        with self.mutable(STANDUPS) as standups:
            standups[team.name][person] = msg.body.replace(str(self.bot_identifier), '')

        self.send(send_to, f'{msg.frm.nick}, got it, thank you.')

