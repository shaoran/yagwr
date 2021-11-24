# yagwr - Yet Another Gitlab Webhooks Runner

[![Documentation Status](https://readthedocs.org/projects/yagwr/badge/?version=latest)](https://yagwr.readthedocs.io/en/latest/?badge=latest)


## Inspiration/Acknowledgments, isn't there enough of these projects already?

That's a fair question. Before I decided to write my own project, I looked for
projects that would fit my needs. And while I found quite a few out there, they were
either to simple or to complex for my needs. One project in particular that got
almost right for my needs is [gitlab-webhook-receiver][gitlab-webhook-receiver].
However I had a few issues with it when I tested it, so I decided to write my
own. I took inspiration on this project, specially the `config.yaml` file, so thank you
for the idea, I will be using a similar approach here.

## Installation

To install this package:

```console
pip install yagwr
```

## Usage

After the installation, a script called ``yagwr`` will be available:

```console
yagwr rules_and_actions.yml
```

For a complete list of all command line options, please execute:

```console
yagwr --help
```

A more detailed documentation can be found here: https://yagwr.readthedocs.io/en/latest/



[gitlab-webhook-receiver]: https://github.com/pstauffer/gitlab-webhook-receiver
