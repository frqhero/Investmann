# Инструкции по деплою ПО в окружение dev-starter-pack-naughty-swanson

[toc]

## Первичный деплой в окружение

В облаке уже должны быть выделены ресурсы. [dev-starter-pack-naughty-swanson](https://sirius-env-registry.website.yandexcloud.net/dev-starter-pack-naughty-swanson.html).

Установите и настройте себе `kubectl` локально прежде, чем двигаться дальше по инструкциям. Подключитесь к кластеру Kubernetes в namespace окружения.

Создайте в кластере дополнительный Secret `django` по такому манифесту:

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: django
  namespace: dev-starter-pack-naughty-swanson
stringData:
  secret_key: "your-secret-key"  # Придумайте свой секретный ключ и укажите его здесь
```

Получите информацию о последнем коммите:

```shell
$ git log -1
# пример вывода:
# commit db06af20bff6df565788a626674f67af379cb863 (HEAD -> main, origin/main, origin/HEAD)
# Author: Sergryap <rs1180@mail.ru>
# Date:   Tue Aug 15 10:50:17 2023 +0500
#
#    Minor testing improvement
```

Убедитесь, что в Container Registry готова сборка для вашего коммита. В описании ресурсов окружения найдите ссылку на консоль управления Container Registry, перейдите по ней, найдите докер-образ с тем же хэшом, что у вашего последнего коммита.

Докер-образы собираются автоматически после пуша в общий репозиторий на GitLab. Процесс занимает до пяти минут. В случае проблем загляните на страницу проекта GitLab во вкладку CI/CD > Pipelines — там можно узнать успешно ли прошли сборка и почитать логи.

Если нашли нужную сборку, то запустите деплой веб-приложения в кластер:

```shell
$ ./deploy.sh
# Пример вывода при успешном деплое:
# …
# Project deployed successfully
# Commit hash of deployed version:: c900c9221d62e24ef227e2c427db5caaed81d051
```

Теперь добавьте суперюзера. Для этого сначала получите имя запущенного пода с помощью команды:

```shell
$ kubectl get pods
# …
# NAME                                 READY   STATUS    RESTARTS   AGE
# django-5bf4545594-sl5c4   1/1     Running   0          7d13h
```

Чтобы попасть в оболочку bash внутри пода запустите команду:

```shell
$ kubectl exec -it django-5bf4545594-sl5c4 bash
# Вместо django-5bf4545594-sl5c4 используйте имя вашего пода
# …
# kubectl exec [POD] [COMMAND] is DEPRECATED and will be removed in a future version. Use kubectl exec [POD] -- [COMMAND] instead.
# root@django-5bf4545594-sl5c4:/opt/app/src#
```

Создайте суперюзера:

```shell
$ ./manage.py createsuperuser
```

Для выхода из bash-оболочки пода введите `exit`.


Админ-панель будет доступна по адресу [https://dev-starter-pack-naughty-swanson.sirius-k8s.dvmn.org/admin](https://dev-starter-pack-naughty-swanson.sirius-k8s.dvmn.org/admin). Для авторизации введите имя и пароль созданного суперюзера.


## Обновление уже развернутого ПО

### Обновить ПО до текущего коммита

Этот вариант деплоя подойдёт вам, если вы хотите выкатить на сервер текущий коммит — тот, в котором сейчас находится ваш репозиторий с кодом.

Получите информацию о последнем коммите:

```shell
$ git log -1
# пример вывода:
# commit db06af20bff6df565788a626674f67af379cb863 (HEAD -> main, origin/main, origin/HEAD)
# Author: Sergryap <rs1180@mail.ru>
# Date:   Tue Aug 15 10:50:17 2023 +0500
#
#    Minor testing improvement
```

Убедитесь, что в Container Registry готова сборка для вашего коммита. В описании ресурсов окружения найдите ссылку на консоль управления Container Registry, перейдите по ней, найдите докер-образ с тем же хэшом, что у вашего последнего коммита.

Докер-образы собираются автоматически после пуша в общий репозиторий на GitLab. Процесс занимает до пяти минут. В случае проблем загляните на страницу проекта GitLab во вкладку CI/CD > Pipelines — там можно узнать успешно ли прошли сборка и почитать логи.

Если нашли нужную сборку, то запустите деплойный скрипт:

```shell
$ ./deploy.sh
# Пример вывода при успешном деплое:
# …
# Project deployed successfully
# Commit hash of deployed version:: c900c9221d62e24ef227e2c427db5caaed81d051
```

Админ-панель будет доступна по адресу [https://dev-starter-pack-naughty-swanson.sirius-k8s.dvmn.org/admin/](https://dev-starter-pack-naughty-swanson.sirius-k8s.dvmn.org/admin/). Логин и пароль суперпользователя можно узнать у менеджера проекта и/или владельца окружения.

Если с последнего деплоя изменился только ConfigMap, но не хэш коммита, то Django Deployment может не заменить изменений и тогда он продолжит работать со старыми настройками. Принудительно перезапустить веб-сервер Django можно командой:

```shell
$ restart.sh
```

### Обновить ПО из другой ветки

Если вы находитесь в одной ветке репозитория с незакоммиченными изменениями, а надо срочно обновить ПО из другой ветки, то воспользуйтесь командой `git stash`. Она позволяет сохранить незакоммиченные изменения  во временном буфере Git.

Положим, сейчас вы находитесь в ветке `initial-branch`, а запустить деплой нужно из другой ветки `another-branch`. Тогда вам помогут следующий команды:

```shell
$ git stash save  # сохранить незакоммиченные изменения во временном буфере
$ git checkout another-branch  # переключиться к другую ветку
```

Теперь обновите приложение по тем же инструкциям, что приведены в разделе [Обновить ПО до текущего коммита](#обновить-по-до-текущего-коммита).

После успешного деплоя вернитесь в прежнюю ветку и восстановите незакоммиченные изменения:

```shell
$ git checkout initial-branch
$ git stash pop
```

## Описание подключения s3 bucket

В окружении должен быть secret с именем `bucket` и ключом `dsn`; в ключе `dsn` находятся параметры подключения в формате:

```yaml
yandex://access_key:secret_key@dev-starter-pack-naughty-swanson/
```

где

- `yandex` - название облачного сервиса. В файле `setting.py` из этой настройки будет установлен параметр `AWS_S3_ENDPOINT_URL` - адрес подключения к S3;
- `access_key` - ключ доступа, например, `ABCDEF1ghIJKlmn2opqR3sTU4`. В файле `setting.py` из этой настройки будет установлен параметр `AWS_ACCESS_KEY_ID`;
- `secret_key` - секретный ключ, например, `ABCDeFGHIg-1KLmnOpqrSTuVw2XYZabC3DeFghI`. В файле `setting.py` из этой настройки будет установлен параметр `AWS_SECRET_ACCESS_KEY`;
- `dev-starter-pack-naughty-swanson` - имя корзины. В файле `setting.py` из этой настройки будет установлен параметр `AWS_STORAGE_BUCKET_NAME`;
