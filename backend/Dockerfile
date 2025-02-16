FROM public.ecr.aws/lambda/python:3.10
ENV PYTHONUNBUFFERED=1

WORKDIR /src
COPY api ./

RUN pip3 install --upgrade pip \
&& pip3 install fastapi \
&& pip3 install "uvicorn[standard]" \
&& pip3 install requests \

ENTRYPOINT ["uvicorn", "main:app", "--host", "0.0.0.0", "--reload"]
