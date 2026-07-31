FROM public.ecr.aws/lambda/python:3.12

COPY requirements.txt .

RUN pip install \
    --no-cache-dir \
    -r requirements.txt

COPY handler.py ${LAMBDA_TASK_ROOT}/

CMD ["handler.the_lambda_handler"]

# FROM public.ecr.aws/lambda/python:3.12
#
# COPY requirements.txt .
#
# RUN pip install -r requirements.txt --target ${LAMBDA_TASK_ROOT}
#
# COPY handler.py ${LAMBDA_TASK_ROOT}
#
# CMD ["handler.the_lambda_handler"]