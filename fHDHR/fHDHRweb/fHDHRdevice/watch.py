import subprocess
import time

from fHDHR.fHDHRerrors import TunerError
import fHDHR.tools


class WatchStream():

    def __init__(self, settings, origserv, tuners):
        self.config = settings
        self.origserv = origserv
        self.tuners = tuners
        self.web = fHDHR.tools.WebReq()

    def direct_stream(self, channel_id, method, channelUri, content_type, duration):

        chunksize = int(self.tuners.config.dict["direct_stream"]['chunksize'])

        if not duration == 0:
            duration += time.time()

        req = self.web.session.get(channelUri, stream=True)

        def generate():
            try:
                for chunk in req.iter_content(chunk_size=chunksize):

                    if not duration == 0 and not time.time() < duration:
                        req.close()
                        print("Requested Duration Expired.")
                        break

                    yield chunk

            except GeneratorExit:
                req.close()
                print("Connection Closed.")
                self.tuners.tuner_close()

        return generate()

    def ffmpeg_stream(self, channel_id, method, channelUri, content_type, duration):

        bytes_per_read = int(self.config.dict["ffmpeg"]["bytes_per_read"])

        ffmpeg_command = [self.config.dict["ffmpeg"]["ffmpeg_path"],
                          "-i", channelUri,
                          "-c", "copy",
                          "-f", "mpegts",
                          "-nostats", "-hide_banner",
                          "-loglevel", "warning",
                          "pipe:stdout"
                          ]

        if not duration == 0:
            duration += time.time()

        ffmpeg_proc = subprocess.Popen(ffmpeg_command, stdout=subprocess.PIPE)

        def generate():
            try:
                while True:

                    if not duration == 0 and not time.time() < duration:
                        ffmpeg_proc.terminate()
                        ffmpeg_proc.communicate()
                        print("Requested Duration Expired.")
                        break

                    videoData = ffmpeg_proc.stdout.read(bytes_per_read)
                    if not videoData:
                        break

                    try:
                        yield videoData

                    except Exception as e:
                        ffmpeg_proc.terminate()
                        ffmpeg_proc.communicate()
                        print("Connection Closed: " + str(e))

            except GeneratorExit:
                ffmpeg_proc.terminate()
                ffmpeg_proc.communicate()
                print("Connection Closed.")
                self.tuners.tuner_close()

        return generate()

    def get_stream(self, channel_id, method, channelUri, content_type, duration):

        try:
            self.tuners.tuner_grab()
        except TunerError:
            print("A " + method + " stream request for channel " +
                  str(channel_id) + " was rejected do to a lack of available tuners.")
            return

        print("Attempting a " + method + " stream request for channel " + str(channel_id))

        if method == "ffmpeg":
            return self.ffmpeg_stream(channel_id, method, channelUri, content_type, duration)
        elif method == "direct":
            return self.direct_stream(channel_id, method, channelUri, content_type, duration)

    def get_stream_info(self, request_args):

        method = str(request_args["method"])
        channel_id = str(request_args["channel"])
        duration = int(request_args["duration"])

        channelUri = self.origserv.get_channel_stream(channel_id)
        if not channelUri:
            return None, None, None, None

        channelUri_headers = self.web.session.head(channelUri).headers
        content_type = channelUri_headers['Content-Type']

        return method, channelUri, content_type, duration
