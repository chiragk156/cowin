# [Depreciated] Cowin Bot
To find vaccine availability and to book slots

Requirements:
Python3
  Libs: requests, svglib==1.0.1, pysimplegui
OS: Windows

How to use:
1. Update details in vaccine_detail.json
2. python <path_to_cowin.py> <path_to_json_file>

How will it work:
1. It will beep when it finds any slot available.
2. Will ask you to provide OTP
3. Enter Captcha
4. Done!

To get notification on telegram/slack/simplepush
Please update telegram/slack/simplepush token defined in cowin.py
