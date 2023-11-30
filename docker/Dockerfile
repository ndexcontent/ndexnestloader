# Use an official Python runtime as a parent image
FROM continuumio/miniconda3

RUN apt-get update
RUN apt-get install -y build-essential 

RUN mkdir /tmp/ndexnestloader
COPY ./ /tmp/ndexnestloader/
RUN pip install /tmp/ndexnestloader

RUN rm -rf /tmp/ndexnestloader

RUN mkdir /ndexnestloader
WORKDIR /ndexnestloader

CMD /bin/echo "To use run: ndexloadnestsubnetworks.py"
