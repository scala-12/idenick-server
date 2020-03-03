UNKNOWN_ALGORITHM = 0
FINGER_ALGORITHM_3 = 1
FINGER_ALGORITHM_1 = 2
FINGER_ALGORITHM_2 = 3
FACE_ALGORITHM = 4
CARD_ALGORITHM = 5
EMPLOYEE_AVATAR = 10

ALGORITHM_TYPE = [
    (UNKNOWN_ALGORITHM, 'Не существующий тип пакета'),

    (FINGER_ALGORITHM_3, 'По отпечатку, возможно в основе его лежит стороний алгоритм'),
    (FINGER_ALGORITHM_1, 'По отпечатку, основной используемый алгоритм идентификации'),
    (FINGER_ALGORITHM_2, 'По отпечатку, не реализован в настоящей сборке'),

    (FACE_ALGORITHM, 'Не распознавание лиц'),
    (EMPLOYEE_AVATAR, 'Фото сотрудника, не используется для авторизации'),

    (CARD_ALGORITHM, 'По номеру карты, дополнительный используемый алгоритм идентификации'),
]
