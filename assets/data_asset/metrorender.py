"""
Support for rendering views....
"""
import matplotlib.pyplot as plt
from matplotlib.pyplot import imshow
import IPython
import time
import json
import base64
import io
import collections
import threading
import pandas as pd
import ipywidgets as widgets
from ipywidgets.widgets.interaction import show_inline_matplotlib_plots
from IPython.core.debugger import set_trace

import urllib3
urllib3.disable_warnings()


def display_digits():
    """Display 100 images rendered configured to run 100 frames a second.
        The 101 frame has a blue 8.
        On my machine this is seems to rendering 50 frames a second.    """
    file = open("data/digits101.gif", "rb")
    image = file.read()
    digits101 = widgets.Image(
        value=image,
        format='png',
        width=300,
        height=400,
    )
    return digits101



class view_to_queue():
    def __init__(self, instance, view_name, output, max_deque=100):
        """move view elements to a queue in a thread
        
        - Spin up thread to read from the view.
        - tuples read goto deque,
        - 
        
        Args:
            instance: streams instance
            view_name : the name of the view 
            output: button rendering region
            max_deque : max number of tuples to hold in queue
        Notes:
            The queue elements are in tuples.
            ```
            tup = <>.tuples.pop()
            list_of tuples : tuples
            ```
            
        """
        self.instance = instance
        self.view_name = view_name
        self.output = output
        self._view = instance.get_views(name=view_name)[0]
        self._view.start_data_fetch()

        # Thread to read from thread write to deque.
        self.tuples = collections.deque(maxlen=100)
        self.event = threading.Event()
        self.button = widgets.Button(description="stop:{}".format(view_name))


    def fetch_metrics(self, debug=False):
        """Thread: fetches elements from queue, monitor event for termination"""
        self.event.set()
        while self.event.is_set():
            tups = self._view.fetch_tuples(max_tuples=100, timeout=2)
            if len(tups) > 0:
                for tup in tups:
                    self.tuples.appendleft(tup)
            else: 
                time.sleep(5)

    def button_clicked(self, b):
        """Done processing clear flag, shutdown process"""
        self.button.description = "Done"
        self.event.clear()
        self._view_WindowUncertainMetrics.stop_data_fetch()

    def start(self):
        self.button.on_click(self.button_clicked)
        self.thread = threading.Thread(target=self.fetch_metrics, name=self.view_name)
        self.thread.start()
        self.output.append_display_data(self.button)

        

    
    
class RenderClassificationMetrics:
  def __init__(self, cameras: list):
    """Render data from the 'ClassificationMetrics' view.
      Args:
        cameras: cameras what that statistics will be rendered for
        
    """
    self.cameras = cameras
    self.class_widgets = {camera:widgets.Output(layout={'border': '1px solid red', 'width': '30%', 'height': '200pt'}) for camera in self.cameras}
    self.class_status_widget = widgets.Label(value="Status", layout={'border': '1px solid green', 'width': '60%'})
    hbox = widgets.HBox([self.class_widgets[ele] for ele in self.class_widgets])
    self.class_dashboard = widgets.VBox([hbox, self.class_status_widget])

  def __call__(self, fetch_tuples):
    """ render the window data 
        Args:
          fetch_tuples: callback to get the next tuples from the ClassificationMetrics view
          returns a list of tuples or None to terminate
    """
    notDone = True
    display(self.class_dashboard)
    cnt = 1
    while notDone:
        try:
            view_metrics = fetch_tuples()
            if view_metrics is None:
              notDone = False
              return
            for raw_metrics in view_metrics:
                metrics = json.loads(raw_metrics)
                for camera in self.cameras:
                    with self.class_widgets[camera]:
                        certain = metrics['camera_metrics'][camera]['certain']
                        uncertain = metrics['camera_metrics'][camera]['uncertain']
                        IPython.display.clear_output(wait=True)
                        df = pd.DataFrame({'uncertain counts': uncertain, 'certain counts': certain}, index=range(len(uncertain)))
                        ax = df.plot.bar(rot=0, title=camera)
                        ax.plot(figsize=[8, 1])
                        show_inline_matplotlib_plots()     
                self.class_status_widget.value = "{} of {} ts: {}".format(cnt, len(view_metrics), metrics['timestamp'])
                cnt += 1
                time.sleep(2)
        except KeyboardInterrupt:
            notDone = False
            raise

        
class deque_synchronous():
    """pop items off queue, call of RenderWindowUncertain - indirectly
       Take three passes at getting data from the queue, then rethrow.
    """
    def __init__(self, tuple_queue, count=3, debug=False):
        self.count = count
        self.debug = debug
        self.tuple_queue = tuple_queue
        
    def get(self):
        self.count -= 1
        if self.debug: print("count:{}".format(self.count))
        if self.count == 0: return None
        for idx in range(3):
            try:
                return [self.tuple_queue.pop()]
            except IndexError:
                time.sleep(3)
            raise
        
            
##
## RenderWindowUncertain
##
class RenderWindowUncertain:
  def __init__(self, output_graphs, cameras: list, status_wait=0):
    """Render data from the 'ClassificationMetrics' view...
      Args
        output_graphs : Output region to display graphs, need this when working within threads
        cameras: cameras that statistics will be rendered. Number of cameras determine the
        width of the dashboard. 
        status_wait : number of seconds to wait after writting a info message into status box.
        
      Notes:
        - Using mathplotlib to display generate/display graphs, problem with graphs not rendering correctly when switched over to threads,
          putting in delay based upon scan of this .. https://github.com/jupyter-widgets/ipywidgets/blob/master/ipywidgets/widgets/interaction.py,
          brute force but it seemed to work - .1 sec did not. 
        - Went to fix pt size , seeing issues with % on the graphs.
          
    """
    self.cameras = cameras
    self.output_graphs = output_graphs
    self.status_wait = status_wait
    
    self.graphic = dict()
    for camera in self.cameras:
        self.graphic[camera] = {
        'images' : widgets.IntProgress(value=7,min=0,max=210,step=1,description='images', bar_style='success', orientation='horizontal'),
        'output': widgets.Output(layout={'border': '1px solid green', 'height': '200pt'}),
        }
    vbox_elements = [[self.graphic[camera]['images'],self.graphic[camera]['output']] for camera in self.cameras]
    vboxes = [widgets.VBox(ele,layout={'border': '1px solid blue'}) for ele in vbox_elements]
    
    self.class_status_widget = widgets.Label(value="Status")
    graphics_hbox = widgets.HBox(vboxes, layout={'border': '2px solid black'})
    
    self.class_dashboard = widgets.VBox([graphics_hbox, self.class_status_widget])

  def render(self, fetch_tuples, process_event):
    """ render the window data 
        Args:
          fetch_tuples: callback to get the next tuples from the ClassificationMetrics view
          returns a list of tuples or None to terminate the processing. 
    """
    #display(self.class_dashboard)
    self.output_graphs.append_display_data(self.class_dashboard)

    notDone = True
    cnt = 0
    clear = False
    process_event.set()
    while process_event.is_set():

        try:
            view_metrics = fetch_tuples.get()
            if view_metrics is None:
              process_event.clear()
              continue
            if len(view_metrics) is 0:
                time.sleep(4.5)
                continue
            for view_metric in view_metrics[0]:
                metrics = json.loads(view_metric)
                for camera in self.cameras:
                    if not process_event.is_set():
                        return
                    with self.graphic[camera]['output']:                        
                        if camera not in metrics['camera_metrics']:
                            self.class_status_widget.value = "info: No data for camera '{}' on this pass.".format(camera)
                            time.sleep(self.status_wait)
                        else:
                            clear = True

                            certain = metrics['camera_metrics'][camera]['certain'][:-1]
                            uncertain = metrics['camera_metrics'][camera]['uncertain'][:-1]
                            # generate images per sec. for bar graph
                            images_per_sec = (sum(certain) + sum(uncertain))/10
                            self.graphic[camera]['images'].value = images_per_sec
                            self.graphic[camera]['images'].description = "img/sec {0:3d}".format(int(images_per_sec))
                            self.graphic[camera]['images'].bar_style = 'warning' if images_per_sec > 100 else 'info'        
                            # generate interdigit proportions: (certain/grand_total, uncertain/grand_total)
                            grand_total = sum(certain) + sum(uncertain)
                            certain_percent = [ (ele/grand_total) * 100 for ele in certain]
                            uncertain_percent = [(ele/grand_total) * 100  for ele in uncertain]


                            IPython.display.clear_output(wait=True)
                            df = pd.DataFrame({'Digit % (uncertain)': uncertain_percent, 'Digit % (certain)': certain_percent}, index=range(len(certain)))
                            ax = df.plot.bar(rot=0, title=camera)
                            ax.set_ylim(0,15)
                            time.sleep(.05)   
                            show_inline_matplotlib_plots()
                    #if clear: self.graphic[camera]['output'].clear_output(wait=True)
                    clear = False


                    self.class_status_widget.value = "{} of {} ts: {}".format(cnt, len(metrics), metrics['timestamp'])
                    time.sleep(0.1)
        except KeyboardInterrupt:
            process_event.clear() # shut down process
        cnt += 1     
#
#   RenderUncertainImages:
#
class RenderUncertainImages:
    """Render data from 'UncertainPrediction' live and slide
       This is for rendering, no fetching here.
       
    """
    def __init__(self, output_uncertain= None, queue_depth=20):
        """Render data from 'UncertainPrediction' live and review
        
        Args:
            output_uncertain : output region dashboard will be displayed. 
            queue_depth : maximum number of elements that can be reviewed.
        """
        self.output_uncertain = output_uncertain
        self.image_index = 0
        self.pause_active = False
        self.view_tuples = collections.deque(maxlen=queue_depth)
        self.active = threading.Event()

        
        self.camera = widgets.Label(value="Camera")
        self.result = widgets.Label(value="Result", layout={'width': '100pt'})
        self.orig = widgets.Output(layout={ 'width': '220pt', 'height': '250pt'})
        self.prep = widgets.Output(layout={ 'width': '200pt', 'height': '250pt'})
        self.digits = [widgets.Label(layout={ 'height': '9%'}) for idx in range(10)]
        self.previous_button = widgets.Button(
            description='Previous',
            disabled=True,
            button_style='info',   # 'success', 'info', 'warning', 'danger' or ''
            tooltip='Review',
            icon='backward',
            layout={'width': '33%'}
        )
        self.stop_button = widgets.Button(
            description='Stop',
            disabled=True,
            button_style='info',   # 'success', 'info', 'warning', 'danger' or ''
            tooltip='Stop continious',
            icon='stop',
            layout={'width': '33%'}
        )
        self.next_button = widgets.Button(
            description='Next',
            disabled=True,
            button_style='info',   # 'success', 'info', 'warning', 'danger' or ''
            tooltip='Review',
            icon='forward',
            layout={'width': '33%'}
        )
        self.status = widgets.Label(value="Status")                
        # enable dashboard keys
        self.previous_button.on_click(self.on_button_clicked)        
        self.next_button.on_click(self.on_button_clicked)
        self.stop_button.on_click(self.on_stop_clicked)

        # compose the the dashboard
        self.digits_vbox = widgets.VBox(self.digits,layout={ 'width': '20%'})
        self.rework_hbox = widgets.HBox([self.prep, self.digits_vbox ])
        self.orig_camera_vbox = widgets.VBox([self.camera, self.orig])
        self.button_hbox = widgets.HBox([self.previous_button, self.stop_button, self.next_button])
        self.rework_button_vbox = widgets.VBox([self.rework_hbox, self.button_hbox])
        self.images_hbox = widgets.HBox([ self.orig_camera_vbox, self.rework_button_vbox],
                                        layout={'border': '1px solid black', 'width':'460pt'} )
        self.dashboard = widgets.VBox([self.images_hbox, self.status])

        if self.output_uncertain is not None:
            self.output_uncertain.append_display_data(self.dashboard)
        
    def set_view_tuples(self, view_tuples):
        # enable the buttons here.
        self.view_tuples = collections.deque(view_tuples, maxlen=20)
        self.image_index = len(self.view_tuples)-1
    
    def display_view(self, tup, status_text):
        """ display the tuple in view, if pause is not active. 
        
        Notes:
            - If pause is not active, load into view_tuples for 'pause' viewing.
            - If pause active don't do anything 
        """
        if self.pause_active:
            return
        self.view_tuples.appendleft(tup)
        self.render_view(json.loads(tup), status_text)
        
    def render_view(self, tup, status_text):
      """ display data in dashboard
      Args:
          tup : the view tuple to be displayed
          status_text : message at the bottom of the screen.
      """
      try:
          ascImg = tup['image']
          prepImg = tup['prepared_image']
          stage = widgets.Output(layout={'border': '1px solid green'})
          oimg = widgets.Image(value=io.BytesIO(base64.b64decode(ascImg)).getvalue(), width=300, height=400)
          self.camera.value = tup['camera']
          self.result.value = str(tup['result_class'])
          for idx,x in enumerate(tup['predictions']):
                self.digits[idx].value = "{:d}: {:3.2f}".format(idx, x)
                self.digits[idx].layout = {'border': '2px solid green', 'height': '7%'} if tup['result_class'] == idx else {'height':'6%'}
                
                
          self.status.value = status_text
          with self.prep:
              imshow(prepImg, cmap=plt.cm.gray_r, interpolation='nearest')
              plt.show()
                
          with self.orig:
              stage.append_display_data(oimg)
                
          self.orig.clear_output(wait=True)
          self.prep.clear_output(wait=True)
            
      except KeyboardInterrupt:
          raise
        
      except Exception as e:
          self.status.value = "Key error : {0:}".format(e)        
            
            
    def on_button_clicked(self, button):
        self.status.value = "on_button"
        """Setup event handler for Previous/Next buttons"""

        if button.description == "Next" and self.image_index < len(self.view_tuples)-1:
            self.image_index += 1
        if button.description == "Previous" and self.image_index != 0:
            self.image_index -= 1
        else:
            if button.description == "Resume":
                self.pause_active = False
                self.pause_button.description = "Pause"
            
        self.render_view(json.loads(self.view_tuples[self.image_index]), "{} of {}".format(self.image_index+1, len(self.view_tuples)))

    def update_status(self, text_message):
        """alternate to direct"""
        self.status.value = text_message

    def interrupt_stopped(self, message):
        """when interrupt occurs setup for review."""
        self.image_index = 0
        self.next_button.disabled = False
        self.previous_button.disabled = False
        self.stop_button.description = ""
        self.stop_button.disabled = True
        self.stop_button.tooltip = "inactive"
        self.render_view(json.loads(self.view_tuples[self.image_index]),message)

        """
        Thread processing
        """
    def on_stop_clicked(self, button):
        """Setup event handler for Stop button"""
        self.status.value = "stop"
        self.active.clear()
        self.next_button.disabled = False
        self.previous_button.disabled = False
        self.stop_button.disabled = True

    def render_thread(self):
        """function being driven by thread, callback to fetched then display"""

        self.active.set()
        while self.active.is_set():
            self.display_view(self.fetch_data_function(), "live")       
        
    def configure_thread(self, fetch_data_function, fetch_data_name):
        """setup the method that will fetch the data to be displayed
        args:
            fetch_data_function: get the data from the queue.
            fetch_data_name : name of the thread to be run.        
        """
        self.fetch_data_function = fetch_data_function
        self.fetch_data_name = fetch_data_name
        
    def start_thread(self):
        """Start thread to fetch and display data, thread stops via button.
        """ 
        self.next_button.disabled = True
        self.previous_button.disabled = True
        self.stop_button.disabled = False
        self.thread = threading.Thread(target=self.render_thread, args=(self.fetch_data_name))
        self.thread.start()

        
        

        

##
##  CorrectionDashboard
##

class CorrectionDashboard():
    """For a list of tuples from 'UncertainPrediction' 
        - display the original image
        - display the scored image
        - display the score
        - radio buttons to change score
        - buttons to move fwd/back of images
        - push chaged scores up the server
        
    Notes: 
        - radio button with confidence needs special procession at the begining.
    """
    def on_radio_clicked(self, radio):
        """ Note - order here, status_widget being declared global before instantiated.
        """
        if radio.type == 'change' and radio.name == 'value' and not self.init_phase and not(self.correct_radio.disabled):
            self.status.value = "update element {}  old:{} new:{}".format(self.image_index, radio.old, radio.new)
            self.corrected_images[self.image_index] = radio.new

    def on_button_clicked(self, button):
        """Setup event handler for Previous/Next/Commit buttons"""
        #set_trace()
        if button.description == "Training Upload":
            image_new_result = [key for key in self.corrected_images.keys() if str(json.loads(self.view_tuples[key])['result_class']) != self.corrected_images[key]]
            self.status.value = "Augment training for {} images".format(len(image_new_result))
            self.progress_rework.max = len(image_new_result)
            cnt = 1             
            for idx in image_new_result:
                self.progress_rework.value = cnt
                cnt += 1
                time.sleep(2)
                self.status.value = "image:{} original result_class:{}  updated result:{}".format(idx, json.loads(self.view_tuples[idx])['result_class'], self.corrected_images[idx])
            self.status.value = "Updated...."
            return
        self.correct_radio.disabled = True
        if button.description == "Next" and self.image_index < len(self.view_tuples)-1:
            self.image_index += 1
        if button.description == "Previous" and self.image_index != 0:
            self.image_index -= 1
        self.display_view(json.loads(self.view_tuples[self.image_index]), "{} of {}".format(len(self.view_tuples), self.image_index))
        self.correct_radio.disabled = False

    
    def __init__(self):
        """ Compose the dashboard images + controls.

        """
        self.corrected_images = collections.defaultdict(str)
        self.image_index = 1
        self.view_tuples = None
        self.init_phase = True

        self.next_rework = widgets.Button(
            description='Next',
            disabled=False,
            button_style='info',  # 'success', 'info', 'warning', 'danger' or ''
            tooltip='Click me',
            icon='forward',
            on_click=self.on_button_clicked
        )
        self.previous_rework = widgets.Button(
            description='Previous',
            disabled=False,
            button_style='info',   # 'success', 'info', 'warning', 'danger' or ''
            tooltip='Click me',
            icon='backward',
            on_click=self.on_button_clicked
        )
        self.commit_rework = widgets.Button(
            description='Training Upload',
            disabled=False,
            button_style='warning',   # 'success', 'info', 'warning', 'danger' or ''
            tooltip='',
            icon='stop',
            on_click=self.on_button_clicked
        )
        self.progress_rework = widgets.IntProgress(
            value=0,
            min=0,
            max=10,
            step=1,
            description='Uploading:',
            bar_style='success',  # 'success', 'info', 'warning', 'danger' or ''
            orientation='horizontal'
        )
        self.correct_radio = widgets.RadioButtons(
            options=['0', '1', '2', '3', '4', '5', '6', '7', '8', '9', 'Camera Error', '2nd Opinion', 'Not a Digit', 'Other'],
            description='Digit',
            orientation='horizontal',
            value='1',
            disabled=False
        )
        
        self.camera = widgets.Label(value="Camera", )
        self.result = widgets.Label(value="Result", )
        self.orig = widgets.Output(layout={'height': '250pt'})
        self.prep = widgets.Output(layout={'height': '250pt'})
        self.status = widgets.Label(value="Status", layout={'width': '60%'})

        self.previous_rework.on_click(self.on_button_clicked)        
        self.next_rework.on_click(self.on_button_clicked)                
        self.correct_radio.observe(self.on_radio_clicked)
        self.commit_rework.on_click(self.on_button_clicked)        
        

        camera_vbox = widgets.VBox([self.camera, self.orig], layout={'border': '1px solid blue', 'width':'33%'})
        predict_vbox = widgets.VBox([self.result, self.prep], layout={'border': '1px solid green', 'width':'33%'})
        radio_vbox = widgets.VBox([self.correct_radio], layout={'border': '1px solid blue','width': '34%'})

        images_hbox = widgets.HBox([camera_vbox, predict_vbox, radio_vbox])
        
        rework_hbox = widgets.HBox([self.previous_rework, self.next_rework, self.commit_rework, self.progress_rework])   
        controls_vbox = widgets.VBox([images_hbox, rework_hbox],layout={'border': '2px solid black'} )
        
        self.dashboard = widgets.VBox([controls_vbox, self.status])

        display(self.dashboard)

    def display_view(self, tup, status_text):
        try:
            ascImg = tup['image']
            prepImg = tup['prepared_image']
            stage = widgets.Output(layout={'border': '1px solid green'})
            oimg = widgets.Image(value=io.BytesIO(base64.b64decode(ascImg)).getvalue(), width=300, height=400)
            self.orig.clear_output(wait=True)
            self.prep.clear_output(wait=True)
            self.camera.value = tup['camera']
            self.result.value = "Model's prediction : {:d}".format(tup['result_class'])
            self.status.value = status_text
            with self.orig:
                stage.append_display_data(oimg)
            with self.prep:
                imshow(prepImg, cmap=plt.cm.gray_r, interpolation='nearest')
                plt.show()
            radio_buttons = ['%d:%9.5f' % (idx, x) for idx, x in enumerate(tup['predictions'])] + ['Camera Error', '2nd Opinion', 'Not a Digit', 'Other']
            self.correct_radio.options = radio_buttons            
            if self.image_index in self.corrected_images:
                self.correct_radio.value = self.corrected_images[self.image_index]
            else:
                self.correct_radio.value = radio_buttons[tup['result_class']]

        except Exception as e:
            self.status.value = "Key error : {0:}".format(e)

    def render_review(self, view_tuples):
        self.view_tuples = view_tuples
        self.image_index = 0
        self.display_view(json.loads(view_tuples[self.image_index]), "Reviewing {} images".format(len(view_tuples)))
        self.init_phase = False
