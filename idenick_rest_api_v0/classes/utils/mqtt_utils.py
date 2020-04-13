"""MQTT utils"""
import base64
import uuid
from dataclasses import dataclass
from enum import Enum
from typing import Optional

import paho.mqtt.client as mqtt

from idenick_app.models import Employee
from idenick_rest_api_v0.serializers import EmployeeSerializers

USE_SSL = False
USERNAME = None
PASSWORD = None
CLEAN_SESSION = True
HOST = 'tgu.idenick.ru'
PORT = 1883
SUBSCRIBE_TOPIC_THREAD = '/BIOID/CLOUD/'
PUBLISH_TOPIC_THREAD = '/BIOID/CLIENT/'
PATH = '/mqtt'


class BiometryType(Enum):
    """Biometry types"""
    FACE = 'FACE'
    FINGER = 'FINGER'
    CARD = 'CARD'


def _get_client_id(client: mqtt.Client):
    return client._client_id.decode('utf-8')


def _on_disconnect(client: mqtt.Client, userdata, rc: int, extra_action=None):
    """default on_disconnect"""
    # pylint: disable=unused-argument
    print(_get_client_id(client) + " disconnected")

    if extra_action is not None:
        extra_action()


def _on_connect(client: mqtt.Client, userdata, flags, rc: int, extra_action=None):
    """default on_connect"""
    # pylint: disable=unused-argument
    print(_get_client_id(client) + " Connected to %s:%s%s with result code %s" % (
        HOST, PORT, PATH, str(rc)))

    if extra_action is not None:
        extra_action(client, rc)


def _on_message(client: mqtt.Client, userdata, msg, extra_action=None):
    """default on_message"""
    # pylint: disable=unused-argument
    payload_str = str(msg.payload)
    print(msg.topic + " " + payload_str)

    if extra_action is not None:
        extra_action(client, msg)


def _on_subscribe(client: mqtt.Client, userdata, mid, granted_qos, extra_action=None):
    """default on_subscribe"""
    # pylint: disable=unused-argument
    print(_get_client_id(client) + ' subscribed')

    if extra_action is not None:
        extra_action(client)


def _on_publish(client, userdata, mid):
    """default on_publish"""
    # pylint: disable=unused-argument
    print(_get_client_id(client) + ((' published (%d)') % (mid)))


class _Connection:
    """operation with connection"""

    def __init__(self, client_id: str, on_connect=None, on_subscribe=None, on_message=None):
        self.connected = None
        self.msg_count = 0

        self._client = mqtt.Client(
            client_id=client_id, clean_session=True, transport="tcp")

        def on_connect_func(client, rc):
            if on_connect is not None:
                on_connect(client)
            self._set_status_connected(rc)

        def on_message_func(client, msg):
            if on_message is not None:
                on_message(client, msg)
            self._msg_inc()

        self._client.on_connect = lambda client, userdata, flags, rc: _on_connect(
            client, userdata, flags, rc, on_connect_func)
        self._client.on_disconnect = lambda client, userdata, rc: _on_disconnect(
            client, userdata, rc, self._set_status_disconnected)
        self._client.on_message = lambda client, userdata, msg: \
            _on_message(client, userdata, msg, on_message_func)
        self._client.on_subscribe = lambda client, userdata, mid, granted_qos: \
            _on_subscribe(client, userdata, mid, granted_qos, on_subscribe)
        self._client.on_publish = _on_publish

    def _set_status(self, status: bool) -> None:
        self.connected = status

    def _set_status_connected(self, rc) -> None:
        self._set_status(rc == 0)

    def _set_status_disconnected(self) -> None:
        self._set_status(False)

    def _msg_inc(self) -> None:
        self.msg_count += 1

    def is_connected(self) -> bool:
        """return connection status"""
        return (self.connected is not None) and self.connected

    def loop(self) -> None:
        """call client.loop(4.0)"""
        try:
            self._client.loop(timeout=4.0)
        except Exception as e:
            # handle any other exception
            print("Error  occured. Arguments {0}.".format(
                e.args))

    def disconnect(self) -> None:
        """call client.disconnect()"""
        self._client.disconnect()

    def connect(self) -> None:
        """call client.connect()"""
        count = 0
        connected = False
        while (not self.is_connected()) and (count < 5):
            try:
                if connected:
                    self.loop()
                else:
                    self._client.connect(HOST, PORT, 60)
                    connected = True
            except Exception as e:
                # handle any other exception
                print("Error  occured. Arguments {0}.".format(
                    e.args))
            count += 1


@dataclass
class CheckResult:
    """biometry exists result"""

    def __init__(self, exists: bool, employee: Optional[Employee] = None):
        self.exists = exists
        self.employee = employee


def _connect_2_topic(
        label: str,
        mqtt_command,
        on_subscribe,
        on_message,
        on_end,
        on_connect_failure=None,
        device_mqtt: Optional[str] = str(uuid.uuid4().int),
        stop_check=None,):
    def on_connect(client):
        client.subscribe(SUBSCRIBE_TOPIC_THREAD + device_mqtt, qos=0)

    def on_subscribe_func(client):
        client.publish(PUBLISH_TOPIC_THREAD + device_mqtt, mqtt_command)
        on_subscribe(client)

    def on_message_func(client, msg):
        on_message(client, msg)

    connection = _Connection(
        client_id=(device_mqtt + ' ' + label),
        on_connect=on_connect,
        on_subscribe=on_subscribe_func,
        on_message=on_message_func,)

    connection.connect()

    _stop_check = (lambda: False) if stop_check is None else stop_check
    if connection.is_connected():
        waiting = 0
        while (waiting < 20) and not _stop_check():
            waiting += 1
            connection.loop()

        on_end()

        connection.disconnect()
    elif on_connect_failure is not None:
        on_connect_failure()


def check_biometry(biometry_bytes) -> CheckResult:
    mqtt_command = ('!FACE_SEARCH,0,' +
                    '\r\n').encode('utf-8') + biometry_bytes
    options = {'subscribed': False, 'employee': None, 'result': None, }

    def on_subscribe(client):
        options.update(subscribed=True)

    def on_message(client, msg):
        payload_str = str(msg.payload)
        if '!SEARCH_OK,' in payload_str:
            result_msg = msg.payload.decode('utf-8').strip()
            options.update(employee=employee_info[3])

            client.disconnect()

    def on_end():
        employee_id = options.get('employee')
        options.update(result=CheckResult(exists=(employee_id is not None),
                                          employee=employee_id,))

    _connect_2_topic(
        label='biometry_search',
        mqtt_command=mqtt_command,
        on_subscribe=on_subscribe,
        on_message=on_message,
        on_end=on_end
    )

    return options.get('result')


@dataclass
class RegistrationResult:
    """biometry registration result"""

    def __init__(self, comment: str, success: bool = False,
                 employee: Optional[Employee] = None):
        self.comment = comment
        self.success = success
        self.employee = employee


def registrate_biometry(employee: Employee, mqtt_id: str, biometry_data: str,
                        biometry_type: BiometryType) -> RegistrationResult:
    """registration biometry to employee"""

    user_info = ('%s,%s,%s'
                 % (employee.last_name, employee.first_name, employee.patronymic,))

    mqtt_command = None
    if biometry_type is BiometryType.FACE:
        biometry_data = base64.b64decode(biometry_data)
        mqtt_command = ('!FACE_ENROLL,0,' + user_info +
                        '\r\n').encode('utf-8') + biometry_data
    elif biometry_type is BiometryType.CARD:
        mqtt_command = ('!IDENROLL,0,' + user_info + ',' +
                        biometry_data + '\r\n').encode('utf-8')
    elif biometry_type is BiometryType.FINGER:
        biometry_data = base64.b64decode(biometry_data)
        mqtt_command = ('!ENROLL,0,' + user_info +
                        '\r\n').encode('utf-8') + biometry_data

    device_mqtt = mqtt_id.replace('/', '')

    options = {'command': None, 'disabled': None,
               'subscribed': False, 'employee': None, 'result': None, }

    def on_subscribe(client):
        options.update(subscribed=True)

    def on_message(client, msg):
        payload_str = str(msg.payload)
        if ('!DUPLICATE,' in payload_str) or ('!ENROLL_OK,' in payload_str)\
                or ('!LOWTQ,' in payload_str):
            result_msg = msg.payload.decode('utf-8').strip()

            if '!LOWTQ,' not in payload_str:
                employee_info = result_msg.split(',')[2:6]

                employee = None
                if '!DUPLICATE,' in result_msg:
                    employee = Employee.objects.filter(id=employee_info[3])
                else:
                    employee = Employee.objects.filter(
                        last_name=employee_info[0], first_name=employee_info[1],
                        patronymic=employee_info[2])

                options.update(employee=employee.first())

            options.update(command=result_msg)
            options.update(disabled='!ENROLL_OK,' not in result_msg)

            client.disconnect()

    def on_end():
        if options.get('disabled') is None:
            options.update(result=RegistrationResult(
                success=False, comment='Результат неизвестен',))
        else:
            employee = None
            if options.get('employee') is not None:
                employee = EmployeeSerializers.ModelSerializer(
                    options.get('employee')).data
            options.update(result=RegistrationResult(success=not options.get('disabled'),
                                                     employee=employee,
                                                     comment=options.get('command'),))

    _connect_2_topic(
        label='biometry_search',
        mqtt_command=mqtt_command,
        on_subscribe=on_subscribe,
        on_message=on_message,
        on_end=on_end,
        stop_check=lambda: (options.get('disabled') is not None),
        on_connect_failure=lambda: (options.update(result=RegistrationResult(
            comment='Не удается подключиться к серверу',)))
    )

    return options.get('result')
