# -*- coding: utf-8 -*-

from __future__ import (absolute_import, print_function, unicode_literals)
import jodel_api
from random import uniform, choice
import datetime
import base64
import pytest
from string import ascii_lowercase
from mock import MagicMock, patch
import builtins
import requests
import os
from flaky import flaky
import time

lat, lng, city = 49.021785, 12.103129, "Regensburg"
test_channel = "WasGehtHeute?"

def delay_rerun(*args):
    time.sleep(3)
    return True


@flaky(max_runs=2, rerun_filter=delay_rerun)
class TestUnverifiedAccount:

    @classmethod
    def setup_class(self):
        self.j = jodel_api.JodelAccount(lat + uniform(-0.01, 0.01), lng + uniform(-0.01, 0.01), city)
        assert isinstance(self.j, jodel_api.JodelAccount)

        r = self.j.get_posts_discussed()
        assert r[0] == 200
        assert "posts" in r[1] and "post_id" in r[1]["posts"][0]
        self.pid = r[1]['posts'][0]['post_id']

    def __repr__(self):
        return "TestUnverifiedAccount <%s, %s>" % (self.j.get_account_data()['device_uid'], self.pid)

    def test_reinitalize(self):
        acc = self.j.get_account_data()
        with pytest.raises(Exception) as excinfo:
            j2 = jodel_api.JodelAccount(lat="a", lng="b", city=13, update_location=True, **acc) 

        assert "Error updating location" in str(excinfo.value)

    def test_refresh_access_token(self):
        r = self.j.refresh_access_token()
        assert r[0] == 200
        assert set(r[1].keys()) == set(["expiration_date", "token_type", "expires_in", "access_token"])

    def test_set_location(self):
        r = self.j.set_location(lat + uniform(-0.01, 0.01), lng + uniform(-0.01, 0.01), city)
        assert r[0] == 204

    def test_read_posts_recent(self):
        r = self.j.get_posts_recent()
        assert r[0] == 200

    def test_get_my_posts(self):
        assert self.j.get_my_voted_posts()[0] == 200
        assert self.j.get_my_replied_posts()[0] == 200
        assert self.j.get_my_pinned_posts()[0] == 200

    def test_newsfeed_after(self):
        r = self.j.get_newsfeed()
        assert r[0] == 200
        assert 'posts' in r[1]

        if not r[1]['posts']:
            pytest.skip("newsfeed returned empty response")

        print("after:", r[1]['posts'][10])
        r2 = self.j.get_newsfeed(after=r[1]['posts'][10]['post_id'])
        assert r2[0] == 200
        assert 'posts' in r2[1]

        # did the after parameter work?
        r2_create_times = [post["created_at"] for post in r2[1]["posts"]]
        assert all([r[1]['posts'][10]["created_at"] > t for t in r2_create_times])

    def test_popular_after(self):
        r = self.j.get_posts_popular()
        assert r[0] == 200
        assert 'posts' in r[1]

        if not r[1]['posts']:
            pytest.skip("posts_popular() returned no posts")

        print("after:", r[1]['posts'][10])
        r2 = self.j.get_posts_popular(after=r[1]['posts'][10]['post_id'])
        assert r2[0] == 200
        assert 'posts' in r2[1]
        if not r2[1]['posts']:
            pytest.skip("posts_popular(after=) returned no posts")

        # did the after parameter work?
        r2_vote_counts = [post["vote_count"] for post in r2[1]["posts"]]
        assert all([r[1]['posts'][10]["vote_count"] >= t for t in r2_vote_counts[1:]])

    def test_channel_after(self):
        r = self.j.get_posts_discussed(channel=test_channel)
        assert r[0] == 200
        assert 'posts' in r[1]

        if not r[1]['posts']:
            pytest.skip("posts_discussed(channel=) returned no posts")

        print("after:", r[1]['posts'][10])
        r2 = self.j.get_posts_discussed(channel=test_channel, after=r[1]['posts'][10]['post_id'])
        assert r2[0] == 200
        assert 'posts' in r2[1]
        if not r2[1]['posts']:
            pytest.skip("posts_discussed(channel=, after=) returned no posts")

        # did the after parameter work?
        r2_child_counts = [post.get("child_count", 0) for post in r2[1]["posts"]]
        assert all([r[1]['posts'][10]["child_count"] + 1 >= t for t in r2_child_counts[1:]])

    def test_get_posts_channel(self):
        r = self.j.get_posts_recent(channel=test_channel)
        assert r[0] == 200
        assert "posts" in r[1]

    def test_get_channels(self):
        r = self.j.get_recommended_channels()
        assert "local" in r[1]
        assert r[0] == 200

        channel = r[1]["local"][0]["channel"]
        assert self.j.get_channel_meta(channel)[0] == 200

    def test_follow_channel(self):
        assert self.j.follow_channel(test_channel)[0] == 204
        assert self.j.unfollow_channel(test_channel)[0] == 204

    def test_get_config(self):
        r = self.j.get_user_config()
        print(r)
        assert r[0] == 200
        assert "verified" in r[1]

        assert self.j.get_karma()[0] == 200

    def test_notifications(self):
        assert self.j.get_notifications_new()[0] == 200
        assert self.j.get_notifications()[0] == 200

    def test_captcha(self):
        r = self.j.get_captcha()
        print(r)
        assert r[0] == 200
        assert "image_url" in r[1]
        assert "key" in r[1]

        assert self.j.submit_captcha(r[1]["key"], [13])[0] == 200

    @patch('jodel_api.JodelAccount.submit_captcha', return_value=(200, {'verified': True}))
    @patch('jodel_api.obtain_input', side_effect="0 1 5 7")
    def test_verify_success(self, input_func, submit_func, capsys):
        self.j.verify_account()

        out, err = capsys.readouterr()
        lines = out.split("\n")
        assert "https://" == lines[0][:8]
        assert "Account successfully verified." == lines[1]

    @patch("jodel_api.obtain_input", side_effect=["0 1 13 25", "asdf asdf", KeyboardInterrupt()])
    def test_verify_fail(self, input_func, capsys):
        with pytest.raises(KeyboardInterrupt) as excinfo:
            self.j.verify_account()
    
        assert "KeyboardInterrupt" in str(excinfo)
        out, err = capsys.readouterr()
        lines = out.split("\n")
        assert "https://" == lines[0][:8]
        assert "Verification failed. Retrying ..." == lines[1]
        assert "https://" == lines[2][:8]
        assert "Invalid input. Retrying ..." == lines[3]
        assert "https://" == lines[4][:8]

    def test_post_details(self):
        r = self.j.get_post_details(self.pid)
        assert r[0] == 200
        assert len(r[1]["children"]) == r[1]["child_count"]

    def test_post_details_v3(self):
        assert self.j.get_post_details_v3(self.pid)[0] == 200
        
    def test_share_url(self):
        assert self.j.get_share_url(self.pid)[0] == 200

    def test_pin(self):
        assert self.j.pin(self.pid)[0] == 200
        assert self.j.unpin(self.pid)[0] == 200

    def test_vote(self):
        assert self.j.upvote(self.pid)[0] == 478
        assert self.j.downvote(self.pid)[0] == 478

    def test_switch_notifications(self):
        r = self.j.enable_notifications(self.pid)
        assert r[0] == 200
        assert r[1]["notifications_enabled"] == True

        r = self.j.disable_notifications(self.pid)
        assert r[0] == 200
        assert r[1]["notifications_enabled"] == False

    @patch('jodel_api.s.request')
    def test_bad_gateway_retry(self, requests_func):
        requests_func.return_value = MagicMock(status_code=502, text="Bad Gateway")

        r = self.j.enable_notifications(self.pid)
        assert r[0] == 502
        assert requests_func.call_count == 3

    @patch('jodel_api.s.request')
    def test_bad_gateway_no_retry(self, requests_func):
        requests_func.return_value = MagicMock(status_code=200, json={'notifications_enabled': True})

        r = self.j.enable_notifications(self.pid)
        assert r[0] == 200
        assert requests_func.call_count == 1

@pytest.mark.skipif(not os.environ.get("JODEL_ACCOUNT"), reason="requires an account uid as environment variable")
class TestVerifiedAccount:

    @classmethod
    @flaky(max_runs=2, rerun_filter=delay_rerun)
    def setup_class(self):
        # this hack only works because we immediately refresh all tokens after instantiating the account
        acc = {'access_token': 'A', 'distinct_id': 'A', 'refresh_token': 'A', 'expiration_date': 1, 
               'device_uid': os.environ.get("JODEL_ACCOUNT")}
        self.j = jodel_api.JodelAccount(lat, lng, city, update_location=False, **acc)
        r = self.j.refresh_all_tokens()
        assert r[0] == 200

        assert self.j.set_location(lat, lng, city)[0] == 204

        # get two post_ids for further testing
        r = self.j.get_posts_discussed()
        assert r[0] == 200
        assert "posts" in r[1] and "post_id" in r[1]["posts"][0]
        self.pid1 = r[1]['posts'][0]['post_id']
        self.pid2 = r[1]['posts'][1]['post_id']
        print(self.pid1, self.pid2)

        # make sure get_my_pinned() isn't empty
        pinned = self.j.get_my_pinned_posts()
        assert pinned[0] == 200
        if len(pinned[1]["posts"]) < 5:
            for post in r[1]["posts"][4:9]:
                self.j.pin(post["post_id"])

        # follow the channel so we can post to it
        assert self.j.follow_channel(test_channel)[0] == 204

    def __repr__(self):
        return "TestUnverifiedAccount <%s, %s>" % (self.pid1, self.pid2)

    @flaky(max_runs=2, rerun_filter=delay_rerun)
    def test_verify(self, capsys):
        self.j.verify_account()
        out, err = capsys.readouterr()
        assert out == "Account is already verified.\n"

    @pytest.mark.xfail(reason="after parameter doesn't work with /mine/ endpoints")
    def test_my_pin_after(self):
        r = self.j.get_my_pinned_posts()
        assert r[0] == 200
        assert 'posts' in r[1]

        if not r[1]['posts']:
            pytest.skip("my_pinned_posts() returned no posts")

        print("after:", r[1]['posts'][3])
        r2 = self.j.get_my_pinned_posts(after=r[1]['posts'][3]['post_id'])
        assert r2[0] == 200
        assert 'posts' in r2[1]
        if not r2[1]['posts']:
            pytest.skip("my_pinned_posts(after=) returned no posts")

        # did the after parameter work?
        r2_create_times = [post["created_at"] for post in r2[1]["posts"]]
        assert all([r[1]['posts'][3]["created_at"] > t for t in r2_create_times])

    @pytest.mark.xfail(reason="after parameter doesn't work with /mine/ endpoints")
    def test_my_voted_after(self):
        r = self.j.get_my_voted_posts()
        assert r[0] == 200
        assert 'posts' in r[1]

        if not r[1]['posts']:
            pytest.skip("my_voted_posts() returned no posts")

        print("after:", r[1]['posts'][3])
        r2 = self.j.get_my_voted_posts(after=r[1]['posts'][3]['post_id'])
        assert r2[0] == 200
        assert 'posts' in r2[1]
        if not r2[1]['posts']:
            pytest.skip("my_voted_posts(after=) returned no posts")

        # did the after parameter work?
        r2_create_times = [post["created_at"] for post in r2[1]["posts"]]
        assert all([r[1]['posts'][3]["created_at"] > t for t in r2_create_times])

    @flaky(max_runs=2, rerun_filter=delay_rerun)
    def test_notifications_read(self):
        assert self.j.get_notifications_new()[0] == 200

        r = self.j.get_notifications()
        print(r)
        assert r[0] == 200
        assert "notifications" in r[1]

        if not r[1]["notifications"]:
            pytest.skip("no notifications returned, cannot mark as read")

        nid = r[1]["notifications"][0]["notification_id"]
        assert self.j.notification_read(notification_id=nid)[0] == 204
        assert self.j.notification_read(post_id=self.pid1)[0] == 204

    @flaky(max_runs=2, rerun_filter=delay_rerun)
    def test_post_message(self):
        color = "FF9908"
        msg = "This is an automated test message. äöü§$%%&àô. Color is #%s. Location is %f:%f. Time is %s. %s" % \
                (color, lat, lng, datetime.datetime.now(), "".join(choice(ascii_lowercase) for _ in range(20)))
        r = self.j.create_post(msg, color=color)
        print(r)
        assert r[0] == 200
        assert "post_id" in r[1]

        p = self.j.get_post_details(r[1]["post_id"])
        assert p[0] == 200
        assert p[1]["color"] == color
        assert p[1]["message"] == msg

        assert self.j.delete_post(r[1]["post_id"])[0] == 204

    @flaky(max_runs=2, rerun_filter=delay_rerun)
    def test_post_reply(self):
        msg = "This is an automated test message. Location is %f:%f. Time is %s. %s" % \
                (lat, lng, datetime.datetime.now(), "".join(choice(ascii_lowercase) for _ in range(20)))
        r = self.j.create_post(msg, ancestor=self.pid1)
        print(r)
        assert r[0] == 200
        assert "post_id" in r[1]

        p = self.j.get_post_details(self.pid1)
        assert p[0] == 200
        assert "children" in p[1]
        print([post["post_id"] for post in p[1]["children"]])
        assert r[1]["post_id"] in [post["post_id"] for post in p[1]["children"]]
        my_post = next(post for post in p[1]["children"] if post["post_id"] == r[1]["post_id"])
        assert my_post["message"] == msg

        assert self.j.delete_post(r[1]["post_id"])[0] == 204

    @flaky(max_runs=2, rerun_filter=delay_rerun)
    def test_post_channel(self):
        color = "9EC41C"
        msg = "This is an automated test message to the channel %s. Color is #%s. Location is %f:%f. Time is %s. %s" % \
                (test_channel, color, lat, lng, datetime.datetime.now(), "".join(choice(ascii_lowercase) for _ in range(20)))
        
        r = self.j.create_post(msg, color=color, channel=test_channel)
        print(r)
        assert r[0] == 200
        assert "post_id" in r[1]

        p = self.j.get_posts_recent(channel=test_channel)
        assert p[0] == 200
        print([post["post_id"] for post in p[1]["posts"]])
        assert r[1]["post_id"] in [post["post_id"] for post in p[1]["posts"]]
        my_post = next(post for post in p[1]["posts"] if post["post_id"] == r[1]["post_id"])
        assert my_post["message"] == msg

        assert self.j.delete_post(r[1]["post_id"])[0] == 204

    @flaky(max_runs=2, rerun_filter=delay_rerun)
    def test_post_channel_img(self):
        color = "9EC41C"
        msg = "This is an automated test message. Color is #%s. Location is %f:%f. Time is %s. %s" % \
                (color, lat, lng, datetime.datetime.now(), "".join(choice(ascii_lowercase) for _ in range(20)))
        with open("test/testimg.png", "rb") as f:
            imgdata = base64.b64encode(f.read()).decode("utf-8") + "".join(choice(ascii_lowercase) for _ in range(10))
        
        r = self.j.create_post(msg, b64img=imgdata, color=color, channel=test_channel)
        print(r)
        assert r[0] == 200
        assert "post_id" in r[1]

        assert self.j.delete_post(r[1]["post_id"])[0] == 204

    @flaky(max_runs=2, rerun_filter=delay_rerun)
    def test_vote(self):
        assert self.j.upvote(self.pid1)[0] == 200
        assert self.j.downvote(self.pid2)[0] == 200
