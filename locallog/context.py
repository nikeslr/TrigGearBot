# locallog/context.py

import uuid
from contextvars import ContextVar

trace_id_var = ContextVar("trace_id", default=None)
user_id_var  = ContextVar("user_id", default=None)
chat_id_var = ContextVar("chat_id", default=None)
log_var = ContextVar("log_var", default=None)

def set_trace_id(value = None):
    if value is None:
        value = str(uuid.uuid4())
    if get_trace_id() is None:
        trace_id_var.set(value)
    return value

def get_trace_id():
    return trace_id_var.get()

def set_user_id(value):
    user_id_var.set(value)

def get_user_id():
    return user_id_var.get()

def set_chat_id(value):
    chat_id_var.set(value)

def get_chat_id():
    return chat_id_var.get()

def set_log(log):
    log_var.set(log)

def get_log():
    return log_var.get()