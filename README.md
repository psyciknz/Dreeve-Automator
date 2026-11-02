# Dreeve Running Title/Description Automation

## Introduction
I enjoy running regularly, and have done so for as long as I have been programming. Strava is a powerful app for athletes to post activities in a simple, effective way. However, the **default titles** provided lack depth, simply denoting the time of day followed by the sport type. The description is also **empty** by default.

But as they made heavy changes to their API, many self hosted projects were excluded from their eco-system and so looked elsewhere.
https://Dreeve.App is one such self hosted replacement.

## Solution
This project aims to automate the title and descriptions of new runs that are detected, using the **Dreeve API**. An input configuration file is taken, and titles and descriptions can be deduced using a set of rules concerning activity distance, duration, date/time and even route, alongside other metrics.

After effective development, a robust command line solution has been implemented, with the following features:
- **Configuration JSON** file with API credentials, markers, title/description templates and a few other settings. Thorough validation will be included for good practice in a vital skill.
- Regular API calls to check for new running activities.
- Fetching and processing run data and generating a title/description, selecting a matching template.
- API call to update the title/description of the activity on Strava.

## Using the Program
Whilst the program is **NOT currrently designed to be generally used**, it is still possible to use it if you are very eager to do so. Note that the setup will not be simplified due to the lack of expectation of usage. No EXE will be generated, and the program will need to be run directly through Python.

It is obviously assumed that you have an existing Strava account. Also remember that this program works for runs only, not cycles or other activity types.

Warning: The program is not simple to use, particularly in terms of input. This is to maximise its flexibility. 

Setup Requirements:
- The program has been designed to work on **Windows and Linux**. There is no reason it should not work on MacOS, but this has not been confirmed.
- Ensure you create your own **Dreeve.App** API key for this program. This is needed because this project relies on the Strava API which is on a per-app basis. Start here: https://docs.dreeve.app./api. 
- Ensure you have **Python 3.10** or above installed.
- Install the required 3rd party libraries in the `requirements.txt` file using pip as usual. See the comments as to why the libraries are included.
- Download and extract the ZIP file in the Release section of this repository.

Assuming the steps above have ben followed, consult the [guide](GUIDE.md) to learn how to use this program.

## Advantages
The program brings the following advantages by sprinkling some automation into Strava:
- **Automatically** generates a **more meaningful** title, and also generate a nice description, rather than the default generic title and empty description.
- It is extremely **flexible** if the input mechanism is well understood.
- **Detailed logging** helps keep track of the program actions.
- It relies on the Strava API which is faster and more **stable** than prohibited web scraping/automation alternatives.
- Source code is available to be modified to adjust to personal circumstances.

## Pitfalls/Warnings
Unsurprisingly, despite its positives, the program currently has countless limitations and weird features that make it quite challenging to use. Some of these limitations could be fixed or minimised with further development, others not so much. It is recommended you tailor your usage to minimise the disruption of these limitations/warnings:
- The entire program is **command-line** based.
- The input mechanism is very **complicated** and verbose, and requires familiarity with JSON.
- **Only runs** are supported by the program, not other activity types like cycles or swims etc.
- Certain metrics that could also be used are **omitted**, such as power and temperature.
- The **route matching is strange** and only an approximation. The storage of latitude/longitude numbers instead of visual points is unhelpful.
- The program requires a Strava Application to work.
- The **weather** integration feature relies on another project in a **weird** way. This is hard to set up and keep working as it rigidly relies on another external software in a clumsy way.

## Disclaimer
Thanks to https://github.com/leoz0214/Strava-Running-Name-Automation for the basis of this project.   And of course thanks to  https://github.com/dreeveapp/dreeve for being such a good platform to migrate to.