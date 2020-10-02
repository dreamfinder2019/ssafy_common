import os
import sys
import gi
import logging
import math
import numpy as np
import ctypes
import cairo

gi.require_version('Gst', '1.0')
gi.require_foreign('cairo')
from gi.repository import Gst, GObject

DEBUG = False

class NNStreamerExample:
    """NNStreamer example for face detection."""

    def __init__(self, argv=None):
        self.loop = None
        self.pipeline = None
        self.running = False
        self.video_caps = None

        self.BOX_SIZE = 4
        self.LABEL_SIZE = 2
        self.DETECTION_MAX = 1917
        self.MAX_OBJECT_DETECTION = 10

        self.Y_SCALE = 10.0
        self.X_SCALE = 10.0
        self.H_SCALE = 5.0
        self.W_SCALE = 5.0

        self.VIDEO_WIDTH = 640
        self.VIDEO_HEIGHT = 480
        self.MODEL_WIDTH = 300
        self.MODEL_HEIGHT = 300

        self.tflite_model = ''
        self.tflite_labels = []
        self.tflite_box_priors = []
        self.detected_objects = []

        if not self.tflite_init():
            raise Exception

        GObject.threads_init()
        Gst.init(argv)

    def run_example(self):
        """Init pipeline and run example.
        :return: None
        """

        print("Run: NNStreamer example for face detection.")

        # main loop
        self.loop = GObject.MainLoop()

        # init pipeline
    #     self.pipeline = Gst.parse_launch(
    #         'v4l2src name=cam_src ! videoconvert ! videoscale ! '
    #         'video/x-raw,width=' + str(self.VIDEO_WIDTH) + ',height=' + str(self.VIDEO_HEIGHT) + ',format=RGB ! tee name=t_raw '
    #         't_raw. ! queue ! videoconvert ! cairooverlay name=tensor_res ! ximagesink name=img_tensor '
    #         't_raw. ! queue ! videoconvert ! tee name=another_split ! '
    #         'queue leaky=2 max-size-buffers=10 ! videoconvert ! videobox name=object1 ! gaussianblur sigma=5 ! videoconvert ! ximagesink sync=false name=video1 '
    #         'another_split. ! queue ! videobox name=object2 ! gaussianblur sigma=5 ! videoconvert ! ximagesink sync=false name=video2 '
    #         'another_split. ! queue ! videobox name=object3 ! gaussianblur sigma=5 ! videoconvert ! ximagesink sync=false name=video3 '
    #         't_raw. ! queue leaky=2 max-size-buffers=2 ! videoscale ! '
    #         'video/x-raw,width=' + str(self.MODEL_WIDTH) + ',height=' + str(self.MODEL_HEIGHT) + ' ! tensor_converter ! '
    #         'tensor_transform mode=arithmetic option=typecast:float32,add:-127.5,div:127.5 ! '
    #         'tensor_filter framework=tensorflow-lite model=' + self.tflite_model + ' ! '
    #         'tensor_sink name=tensor_sink'
    #    )

    #     # init pipeline
    #     self.pipeline = Gst.parse_launch(
    #         'v4l2src name=cam_src ! videoconvert ! videoscale ! '
    #         'video/x-raw,width=' + str(self.VIDEO_WIDTH) + ',height=' + str(self.VIDEO_HEIGHT) + ',format=RGB ! tee name=t_raw '
    #         't_raw. ! queue ! videoconvert ! cairooverlay name=tensor_res ! ximagesink name=img_tensor '
    #         't_raw. ! queue ! videoconvert ! tee name=another_split ! '
    #         'queue leaky=2 max-size-buffers=10 ! videoconvert ! videobox name=object1 ! videoscale ! videoconvert ! ximagesink sync=false name=video1 '
    #         'another_split. ! queue ! videobox name=object2 ! videoscale ! videoconvert ! ximagesink sync=false name=video2 '
    #         'another_split. ! queue ! videobox name=object3 ! videoscale ! videoconvert ! ximagesink sync=false name=video3 '
    #         'another_split. ! queue ! videobox name=object4 ! videoscale ! videoconvert ! ximagesink sync=false name=video4 '
    #         'another_split. ! queue ! videobox name=object5 ! videoscale ! videoconvert ! ximagesink sync=false name=video5 '
    #         't_raw. ! queue leaky=2 max-size-buffers=2 ! videoscale ! '
    #         'video/x-raw,width=' + str(self.MODEL_WIDTH) + ',height=' + str(self.MODEL_HEIGHT) + ' ! tensor_converter ! '
    #         'tensor_transform mode=arithmetic option=typecast:float32,add:-127.5,div:127.5 ! '
    #         'tensor_filter framework=tensorflow-lite model=' + self.tflite_model + ' ! '
    #         'tensor_sink name=tensor_sink'
    #    )

        # init pipeline
        self.pipeline = Gst.parse_launch(
            'v4l2src name=cam_src ! videoconvert ! videoscale ! '
            'video/x-raw,width=' + str(self.VIDEO_WIDTH) + ',height=' + str(self.VIDEO_HEIGHT) + ',format=RGB ! tee name=t_raw '
            't_raw. ! queue ! videoconvert ! cairooverlay name=tensor_res ! ximagesink name=img_tensor '
            't_raw. ! queue ! videoconvert ! tee name=another_split ! '
            'queue leaky=2 max-size-buffers=10 ! '
            'videoconvert ! videobox name=object1 ! videoscale ! videoconvert ! ximagesink sync=false name=video1 '
            'another_split. ! queue ! videobox name=object2 ! videoscale ! videoconvert ! ximagesink sync=false name=video2 '
            'another_split. ! queue ! videobox name=object3 ! videoscale ! videoconvert ! ximagesink sync=false name=video3 '
            'another_split. ! queue ! videobox name=object4 ! videoscale ! videoconvert ! ximagesink sync=false name=video4 '
            'another_split. ! queue ! videobox name=object5 ! videoscale ! videoconvert ! ximagesink sync=false name=video5 '
            't_raw. ! queue leaky=2 max-size-buffers=2 ! videoscale ! '
            'video/x-raw,width=' + str(self.MODEL_WIDTH) + ',height=' + str(self.MODEL_HEIGHT) + ' ! tensor_converter ! '
            'tensor_transform mode=arithmetic option=typecast:float32,add:-127.5,div:127.5 ! '
            'tensor_filter framework=tensorflow-lite model=' + self.tflite_model + ' ! '
            'tensor_sink name=tensor_sink'
       )

        # bus and message callback
        bus = self.pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect('message', self.on_bus_message)

        # tensor sink signal : new data callback
        tensor_sink = self.pipeline.get_by_name('tensor_sink')
        tensor_sink.connect('new-data', self.new_data_cb)

        tensor_res = self.pipeline.get_by_name('tensor_res')
        tensor_res.connect('draw', self.draw_overlay_cb)
        tensor_res.connect('caps-changed', self.prepare_overlay_cb)

        # start pipeline
        self.pipeline.set_state(Gst.State.PLAYING)
        self.running = True

        # run main loop
        self.loop.run()

        # quit when received eos or error message
        self.running = False
        self.pipeline.set_state(Gst.State.NULL)

        bus.remove_signal_watch()

    def tflite_init(self):
        """
        :return: True if successfully initialized
        """
        tflite_model = 'detect_face.tflite'
        tflite_label = 'labels_face.txt'
        tflite_box_prior = "box_priors.txt"

        current_folder = os.path.dirname(os.path.abspath(__file__))
        model_folder = os.path.join(current_folder, 'tflite_model')

        self.tflite_model = os.path.join(model_folder, tflite_model)
        if not os.path.exists(self.tflite_model):
            logging.error('cannot find tflite model [%s]', self.tflite_model)
            return False

        label_path = os.path.join(model_folder, tflite_label)
        try:
            with open(label_path, 'r') as label_file:
                for line in label_file.readlines():
                    self.tflite_labels.append(line)
        except FileNotFoundError:
            logging.error('cannot find tflite label [%s]', label_path)
            return False

        box_prior_path = os.path.join(model_folder, tflite_box_prior)
        try:
            with open(box_prior_path, 'r') as box_prior_file:
                for line in box_prior_file.readlines():
                    datas = list(map(float, line.split()))
                    self.tflite_box_priors.append(datas)
        except FileNotFoundError:
            logging.error('cannot find tflite label [%s]', box_prior_path)
            return False

        logging.info('finished to load labels, total [%d]', len(self.tflite_labels))
        logging.info('finished to load box_priors, total [%d]', len(self.tflite_box_priors))
        return True

    # @brief Callback for tensor sink signal.
    def new_data_cb(self, sink, buffer):
        if self.running:
            if buffer.n_memory() != 2:
                return False

            #  tensor type is float32.
            #  [0] dim of boxes > BOX_SIZE : 1 : DETECTION_MAX : 1 (4:1:1917:1)
            #  [1] dim of labels > LABEL_SIZE : DETECTION_MAX : 1 (91:1917:1)

            # To use boxes and detections in python properly, bytestrings that are based on float32 must be decoded into float list.

            # boxes
            mem_boxes = buffer.peek_memory(0)
            result1, info_boxes = mem_boxes.map(Gst.MapFlags.READ)
            if result1:
                assert info_boxes.size == self.BOX_SIZE * self.DETECTION_MAX * 4, "Invalid info_box size"
                decoded_boxes = list(np.fromstring(info_boxes.data, dtype=np.float32))  # decode bytestrings to float list
            
            # detections
            mem_detections = buffer.peek_memory(1)
            result2, info_detections = mem_detections.map(Gst.MapFlags.READ)
            if result2:
                assert info_detections.size == self.LABEL_SIZE * self.DETECTION_MAX * 4, "Invalid info_detection size"
                decoded_detections = list(np.fromstring(info_detections.data, dtype=np.float32)) # decode bytestrings to float list

            idx = 0
            
            boxes = []
            for _ in range(self.DETECTION_MAX):
                box = []    
                for _ in range(self.BOX_SIZE):
                    box.append(decoded_boxes[idx])
                    idx += 1
                boxes.append(box)

            idx = 0

            detections = []
            for _ in range(self.DETECTION_MAX):
                detection = []    
                for _ in range(self.LABEL_SIZE):
                    detection.append(decoded_detections[idx])
                    idx += 1
                detections.append(detection)

            self.get_detected_objects(detections, boxes)

            mem_boxes.unmap(info_boxes)
            mem_detections.unmap(info_detections)

    def iou(self, A, B):
        x1 = max(A['x'], B['x'])
        y1 = max(A['y'], B['y'])
        x2 = min(A['x'] + A['width'], B['x'] + B['width'])
        y2 = min(A['y'] + A['height'], B['y'] + B['height'])
        w = max(0, (x2 - x1 + 1))
        h = max(0, (y2 - y1 + 1))
        inter = float(w * h)
        areaA = float(A['width'] * A['height'])
        areaB = float(B['width'] * B['height'])
        o = float(inter / (areaA + areaB - inter))
        return o if o >= 0 else 0

    def nms(self, detected):
        threshold_iou = 0.5
        detected = sorted(detected, key=lambda a: a['prob'])
        boxes_size = len(detected)

        _del = [False for _ in range(boxes_size)]

        for i in range(boxes_size):
            if not _del[i]:
                for j in range(i + 1, boxes_size):
                    if self.iou(detected[i], detected[j]) > threshold_iou:
                        _del[j] = True

        # update result
        self.detected_objects.clear()

        for i in range(boxes_size):
            if not _del[i]:
                self.detected_objects.append(detected[i])

                if DEBUG:
                    print("==============================")
                    print("LABEL           : {}".format(self.tflite_labels[detected[i]["class_id"]]))
                    print("x               : {}".format(detected[i]["x"]))
                    print("y               : {}".format(detected[i]["y"]))
                    print("width           : {}".format(detected[i]["width"]))
                    print("height          : {}".format(detected[i]["height"]))
                    print("Confidence Score: {}".format(detected[i]["prob"]))

                # left=80 right=50 top=120 bottom=200
                
                current_detect_idx = len(self.detected_objects)
                target_box = self.pipeline.get_by_name(f'object{current_detect_idx}')
                x = detected[i]["x"] * self.VIDEO_WIDTH // self.MODEL_WIDTH
                y = detected[i]["y"] * self.VIDEO_HEIGHT // self.MODEL_HEIGHT
                width = detected[i]["width"] * self.VIDEO_WIDTH // self.MODEL_WIDTH
                height = detected[i]["height"] * self.VIDEO_HEIGHT // self.MODEL_HEIGHT

                target_box.set_property('left', x)
                target_box.set_property('top', y)
                target_box.set_property('right', self.VIDEO_WIDTH - x - width)
                target_box.set_property('bottom', self.VIDEO_HEIGHT - y - height)
                    


    def get_detected_objects(self, detections, boxes):
        threshold_score = 0.5
        detected = list()

        for d in range(self.DETECTION_MAX):
            ycenter = boxes[d][0] / self.Y_SCALE * self.tflite_box_priors[2][d] + self.tflite_box_priors[0][d]
            xcenter = boxes[d][1] / self.X_SCALE * self.tflite_box_priors[3][d] + self.tflite_box_priors[1][d]
            h = math.exp(boxes[d][2] / self.H_SCALE) * self.tflite_box_priors[2][d]
            w = math.exp(boxes[d][3] / self.W_SCALE) * self.tflite_box_priors[3][d]

            ymin = ycenter - h / 2.0
            xmin = xcenter - w / 2.0
            ymax = ycenter + h / 2.0
            xmax = xcenter + w / 2.0

            x = xmin * self.MODEL_WIDTH
            y = ymin * self.MODEL_HEIGHT
            width = (xmax - xmin) * self.MODEL_WIDTH
            height = (ymax - ymin) * self.MODEL_HEIGHT

            for c in range(1, self.LABEL_SIZE):
                score = 1.0 / (1.0 + math.exp(-detections[d][c]))

                # This score cutoff is taken from Tensorflow's demo app.
                # There are quite a lot of nodes to be run to convert it to the useful possibility
                # scores. As a result of that, this cutoff will cause it to lose good detections in
                # some scenarios and generate too much noise in other scenario.

                if score < threshold_score:
                    continue

                obj = {
                    'class_id': c,
                    'x': x,
                    'y': y,
                    'width': width,
                    'height': height,
                    'prob': score
                }

                detected.append(obj)
        
        self.nms(detected)

    # @brief Store the information from the caps that we are interested in.
    def prepare_overlay_cb(self, overlay, caps):
        self.video_caps = caps

    # @brief Callback to draw the overlay.
    def draw_overlay_cb(self, overlay, context, timestamp, duration):
        if self.video_caps == None or not self.running:
            return

        # mutex_lock alternative required
        detected = self.detected_objects
        # mutex_unlock alternative needed
        
        drawed = 0
        context.select_font_face('Sans', cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        context.set_font_size(20.0)

        for obj in detected:
            label = self.tflite_labels[obj['class_id']][:-1]
            x = obj['x'] * self.VIDEO_WIDTH // self.MODEL_WIDTH
            y = obj['y'] * self.VIDEO_HEIGHT // self.MODEL_HEIGHT
            width = obj['width'] * self.VIDEO_WIDTH // self.MODEL_WIDTH
            height = obj['height'] * self.VIDEO_HEIGHT // self.MODEL_HEIGHT

            # draw rectangle
            context.rectangle(x, y, width, height)
            context.set_source_rgb(1, 0, 0)
            context.set_line_width(1.5)
            context.stroke()
            context.fill_preserve()

            # draw title
            context.move_to(x + 5, y + 25)
            context.text_path(label)
            context.set_source_rgb(1, 0, 0)
            context.fill_preserve()
            context.set_source_rgb(1, 1, 1)
            context.set_line_width(0.3)
            context.stroke()
            context.fill_preserve()

            drawed += 1
            if drawed >= self.MAX_OBJECT_DETECTION:
                break

    def on_bus_message(self, bus, message):
        """Callback for message.
        :param bus: pipeline bus
        :param message: message from pipeline
        :return: None
        """
        if message.type == Gst.MessageType.EOS:
            logging.info('received eos message')
            self.loop.quit()
        elif message.type == Gst.MessageType.ERROR:
            error, debug = message.parse_error()
            logging.warning('[error] %s : %s', error.message, debug)
            self.loop.quit()
        elif message.type == Gst.MessageType.WARNING:
            error, debug = message.parse_warning()
            logging.warning('[warning] %s : %s', error.message, debug)
        elif message.type == Gst.MessageType.STREAM_START:
            logging.info('received start message')
        elif message.type == Gst.MessageType.QOS:
            data_format, processed, dropped = message.parse_qos_stats()
            format_str = Gst.Format.get_name(data_format)
            logging.debug('[qos] format[%s] processed[%d] dropped[%d]', format_str, processed, dropped)

    def set_window_title(self, name, title):
        """Set window title.
        :param name: GstXImageasink element name
        :param title: window title
        :return: None
        """
        element = self.pipeline.get_by_name(name)
        if element is not None:
            pad = element.get_static_pad('sink')
            if pad is not None:
                tags = Gst.TagList.new_empty()
                tags.add_value(Gst.TagMergeMode.APPEND, 'title', title)
                pad.send_event(Gst.Event.new_tag(tags))

if __name__ == '__main__':
    example = NNStreamerExample(sys.argv[1:])
    example.run_example()