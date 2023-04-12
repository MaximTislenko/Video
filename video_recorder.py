import os
import cv2
import time
from datetime import datetime
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
import tzlocal
import ffmpeg

class VideoRecorder:
    def __init__(self, camera, record_till_length=None, record_till_time=None, scheduler=False, cron_string=None, show=False, compress=False, v_bitrate=None, resolution=None):

        self.now = datetime.now()
        self.timezone = str(tzlocal.get_localzone())

        # имя камеры и ссылка на rtsp поток
        self.camera = camera

        self.record_till_length = record_till_length
        self.record_till_time = record_till_time

        assert self.record_till_length or self.record_till_time, 'Должен быть активирован хотя бы один тип ограничения времени записи видео: по длительности или по времени окончания, или оба'

        # Настройки планировщика
        self.scheduler = scheduler
        self.cron_string = cron_string  # CRON строка в виде '0 10 * * *' - ежедневный запуск в 10:00

        # Нужно ли отображать видео
        self.show = show

        # Настройки сжатия видео
        self.compress = compress
        self.v_bitrate = (str(v_bitrate) + 'k') if v_bitrate else 0  # Желаемый битрейт указывается цифрами в kbps, например 1000 -> 1000 kbps
        self.resolution = resolution  # Разрешение указывается в формате: '1280:720', '1280:-1', '-1:720'

        self.vid = cv2.VideoCapture(self.camera[1])
        self.width = int(self.vid.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.height = int(self.vid.get(cv2.CAP_PROP_FRAME_HEIGHT))
        print('Ширина и высота кадра:', self.width, self.height)
        self.fps = int(self.vid.get(cv2.CAP_PROP_FPS))        
        print('Количество кадров в секунду:', self.fps)

        assert self.fps > 0, 'Видео поток в данный момент не имеет данные, попробуйте запустить позже'

        self.codec = cv2.VideoWriter_fourcc(*'mp4v')

        self.files = []

    def get_finish_time(self, _time: str):
        try:
            _time = time.strptime(_time, '%H:%M:%S')
        except ValueError:
            print('\nВремя должно задаваться в формате чч:мм:сс, например "20:30:00"\n')
        # Значения для ограничения по времени завершения
        # Например, записывать до 20:30:00
        rec_t_hour = _time.tm_hour  # часы
        rec_t_min = _time.tm_min  # минуты
        rec_t_sec = _time.tm_sec  # секунды
        self.finish_time = datetime(self.now.year, self.now.month, self.now.day, rec_t_hour, rec_t_min, rec_t_sec)

        return self.finish_time

    def seconds_to_hms(self, seconds):
        h = int(seconds // 3600)
        seconds = seconds % 3600
        m = int(seconds // 60)
        s = int(seconds % 60)
        return h, m, s

    def count_finish(self, h, m, s, fps):
        return (h * 3600 + m * 60 + s) * fps

    def get_finish_frame(self, _time: str):
        # Ниже нужно указать длительность записи видео.
        # Значения для ограничения по длительности
        # Например, записывать 8 часов подряд
        try:
            _time = time.strptime(_time, '%H:%M:%S')
        except ValueError:
            print('\nВремя должно задаваться в формате чч:мм:сс, например "00:00:30"\n')
        rec_l_hour = _time.tm_hour  # часы
        rec_l_min = _time.tm_min  # минуты
        rec_l_sec = _time.tm_sec  # секунды

        self.finish_frame = self.count_finish(rec_l_hour, rec_l_min, rec_l_sec, self.fps)

        return self.finish_frame

    def reconnect(self):
        self.vid.release()
        self.out.release()
        cv2.destroyAllWindows()
        print('Попытка переподключения')
        self.now = datetime.now()
        self.vid = cv2.VideoCapture(self.camera[1])
        if self.vid.isOpened():

            self.width = int(self.vid.get(cv2.CAP_PROP_FRAME_WIDTH))
            self.height = int(self.vid.get(cv2.CAP_PROP_FRAME_HEIGHT))
            print('Ширина и высота кадра:', self.width, self.height)
            self.fps = int(self.vid.get(cv2.CAP_PROP_FPS))            
            print('Количество кадров в секунду:', self.fps)
            self.codec = cv2.VideoWriter_fourcc(*'mp4v')
            video_name = f'{self.now.strftime("%d_%m_%Y_%H_%M_%S")}.mp4'
            self.video_output_path = os.path.join(self.camera_dir, video_name)
            self.out = cv2.VideoWriter(self.video_output_path, self.codec, self.fps, (self.width, self.height))
            self.files.append(self.video_output_path)

    def compress_videos(self, input_file_list, v_bitrate, resolution):
        for file in input_file_list:
            parent_dir, file_name = os.path.split(file)[0], os.path.split(file)[-1]
            output_dir = os.path.join(parent_dir, 'compressed')
            if not os.path.exists(output_dir):
                os.mkdir(output_dir)
            out_file = os.path.join(output_dir, file_name)
            if resolution:
                width, height = [int(x) for x in resolution.split(':')]
                print(f'Ширина и высота сжатого видео: {width} {height}')
            else:
                width, height = -1, -1

            try:
                out, err = (
                    ffmpeg
                    .input(file)
                    .filter('scale', width, height)
                    .output(out_file, video_bitrate=v_bitrate)
                    .run(capture_stderr=True)
                )
            except ffmpeg.Error as e:
                print(e.stderr)
                print(f"{err=}")

            if os.path.isfile(out_file) and os.path.getsize(out_file) > 0:
                print('Сжатое видео сохранено по пути:', out_file)
                print('Размер исходного файла:', os.path.getsize(file) >> 20, 'MB')
                print('Размер сжатого файла:', os.path.getsize(out_file) >> 20, 'MB')

    def record_video(self):
        self.start_work = time.time()

        # Папка, в которую записываются видео
        self.videos_dir = "Records"

        if not os.path.exists(self.videos_dir):
            os.mkdir(self.videos_dir)

        self.camera_dir = os.path.join(self.videos_dir, self.camera[0])

        if not os.path.exists(self.camera_dir):
            os.mkdir(self.camera_dir)

        video_name = f'{self.now.strftime("%d_%m_%Y_%H_%M_%S")}.mp4'
        self.video_output_path = os.path.join(self.camera_dir, video_name)
        self.out = cv2.VideoWriter(self.video_output_path, self.codec, self.fps, (self.width, self.height))
        self.files.append(self.video_output_path)

        if self.record_till_length:
            finish_frame = self.get_finish_frame(self.record_till_length)
        if self.record_till_time:
            finish_time = self.get_finish_time(self.record_till_time)

        count_frames = 0
        print('Запись началась')
        while True:
            success, image = self.vid.read()
            count_frames += 1

            if not success:
                print('! Потеряна связь с камерой, ждём восстановления')
                time.sleep(1)
                self.reconnect()
                if not self.vid.isOpened():
                    continue
            else:
                if self.record_till_length:

                    if count_frames > finish_frame:
                        break

                if self.record_till_time:

                    if datetime.now() > finish_time:
                        print(f"{datetime.now()=}")
                        print(f"{self.finish_time=}")
                        break

                self.out.write(image)

                if self.show:
                    cv2.imshow("RTSP", image)
                    k = cv2.waitKey(5)
                    if k == ord("q"):
                        break

                already_record = count_frames / self.fps
                if already_record % 300 == 0:
                    print(f'Записано {int(already_record // 300) * 5} минут видео')

        print('Завершение записи видео')
        self.vid.release()
        self.out.release()
        cv2.destroyAllWindows()

        print('Всего запись видео заняла {} часов {} минут {} секунд'.format(*self.seconds_to_hms(time.time() - self.start_work)))

        for file in self.files:
            if os.path.exists(file):
                print('Видео сохранено по пути:', file)
            else:
                print('Видео не было сохранено !')
        if self.compress:
            print('Сжатие видео')
            self.compress_videos(self.files, self.v_bitrate, self.resolution)

    def record(self):
        if self.scheduler:
            print('Запущен планировщик')
            print(f'{self.cron_string=}')
            self.scheduler = BlockingScheduler()
            self.scheduler.add_job(
                self.record_video,
                CronTrigger.from_crontab(self.cron_string, timezone=self.timezone)
            )
            self.scheduler.start()
        else:
            self.record_video()


# Здесь указать номер камеры из списка ниже,
# по которой будет идти запись
camera_ind = 5

# Список камер (имя камеры и ссылка на rtsp поток)
cameras = [
    ('Рабочие столы магазин', 'rtsp://admin:@80.242.77.56:559/Streaming/Channels/102'),  # 0   
    ('торт_2', 'rtsp://admin:LBSAVI@109.188.114.15:554/Streaming/channels/1'), #1
    ('565', 'rtsp://admin:19922002t@109.74.133.138:565/RVi/1/1'),  #2
    ('букмекер_560', 'rtsp://admin:19922002t@109.74.133.138:560/RVi/1/1'), # 3 
    ('тц_мебель', 'rtsp://admin:@90.188.224.180/user=admin_password=tlJwpbo6_channel=1_stream=0.sdp?real_stream'), #4
    ('factory', 'rtsp://admin:0534146@91.146.33.109:554/ch01/0') #5
]

# video1 = VideoRecorder(camera=camera, record_till_length='0:0:10', scheduler=True, cron_string='41 17 * * *', show=True)
# video1 = VideoRecorder(camera=camera, record_till_length='0:0:10', compress=True)
# video1 = VideoRecorder(camera=camera, record_till_time='16:18:30', compress=True)
video = VideoRecorder(
    camera=cameras[camera_ind],
    record_till_length='0:30:00',
    scheduler=True,
    cron_string='58 * * * *',
    compress=False,
    resolution='1280:720',
    v_bitrate=1000,
    show=True
    )
video.record()

"""
Установка модулей:
pip install -r reqirements.txt

Обязательные параметры для запуска:
camera=cameras[camera_ind] из списка камер. либо можно передать произвольный поток в виде кортежа ('<название потока>', <адрес rtsp потока>)
record_till_time - будет записывать до указанного времени, формат 'чч:мм:сс',
либо 
record_till_length - будет записывать до указанной длины видео, формат 'чч:мм:сс'

Необязательные параметры:
compress=True|False - для сжатия после записи указать True,
при этом можно указать желаемый битрейт в kbps, только цифры, например v_bitrate=1000 -> 1000 kbps
для изменения разрешения ключ resolution= формате: '1280:720', '1280:-1' или '-1:720'

Для запуска с планировщиком указать ключ scheduler=True и cron_string в формате '* * * * *'
Например '0 20 * * *' будет запускать каждый день в 20:00

show=True будет показывать видео с камеры в процессе записи

Создаем инстанс класса:
video = VideoRecorder(camera=cameras[0], record_till_length='0:10:00', scheduler=True, cron_string='0 20 * * *')
запись первого потока 'Рабочие столы магазин', длина записи 10 минут, запуск по планировщику в 20:00 каждый день

Запуск записи:
video.record()
"""
