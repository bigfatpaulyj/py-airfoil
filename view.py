from euclid import *
from pyglet.gl import *
from control import Controller

class ViewType:
    def __init__(self, name):
        self.__name=name

EXTERNAL=ViewType('external view')
INTERNAL=ViewType('internal view')

class Camera(object):
    TYPE=EXTERNAL

    def __init__(self, plane, offset, zoom=10):
        self._plane=plane
        self.pos = Point3(0,0,0)
        self.eye = Point3(0,0,0)
        self.zen = Point3(0,0,0)
        self._offset=offset
        (self._xrot, self._zrot, self._zoom)=(0.0, 0.0, zoom)

    def activate(self):
        pass

    @property
    def vantage(self):
        return (self._xrot, self._zrot, self._zoom)

    @vantage.setter
    def vantage(self, (xrot, zrot, zoom)):
        if zoom<1:
            zoom=1
        if zoom>40:
            zoom=40
        (self._xrot, self._zrot, self._zoom)=(xrot, zrot, zoom)

    def getCameraVectors(self):
        return [self.pos, self.eye, self.zen]

    def activate(self, pos, eye, zen):
        self.pos = pos
        self.eye = eye
        self.zen = zen
        gluLookAt(eye.x, eye.y, eye.z,
                  pos.x, pos.y, pos.z,
                  zen.x, zen.y, zen.z)
        
class FollowCam(Camera):
    def __init__(self, plane, offset=Vector3(-10.0, 5.0, 0.2), zoom=10):
        Camera.__init__(self, plane, offset, zoom)

    def activate(self):
        att = self._plane.getAttitude()
        adjAtt = Quaternion.new_rotate_euler( self._zrot/180.0*math.pi, self._xrot/180.0*math.pi, 0.0)
        cameraAdjust = adjAtt * self._offset * self._zoom
        pos = self._plane.getPos()
        eye = pos + cameraAdjust
        zen = adjAtt * Vector3(0.0,1.0,0.0)
        super(FollowCam, self).activate(pos,eye,zen)

class FixedCam(Camera):
    def __init__(self, plane, offset=Vector3(-10.0, 10.0, 0.2), zoom=10):
        Camera.__init__(self, plane, offset, zoom)

    def activate(self):
        att = self._plane.getAttitude()
        #print 'att: '+str(att)
        adjAtt = Quaternion.new_rotate_euler( self._zrot/180.0*math.pi, self._xrot/180.0*math.pi, 0.0)
        cameraAdjust = att * adjAtt * self._offset * self._zoom
        #pos is where you want to look
        pos = self._plane.getPos()
        #pos = pos + (att * Vector3(200.0, 0.0, 0.0))
        eye = pos + cameraAdjust
        zen = att * adjAtt * Vector3(0.0,1.0,0.0)
        super(FixedCam, self).activate(pos,eye,zen)

class InternalCam(FixedCam):
    TYPE=INTERNAL

    def __init__(self, plane, offset=Vector3(-10.0, 0.0, 0.0), zoom=1):
        FixedCam.__init__(self, plane, offset, zoom)    

    @property
    def vantage(self):
        return (self._xrot, self._zrot, self._zoom)

    @vantage.setter
    def vantage(self, (xrot, zrot, zoom)):
        # disable zoom
        (self._xrot, self._zrot)=(xrot, zrot)
        self._zoom=zoom

class View(pyglet.event.EventDispatcher):
    __FOLLOW=0
    __FIXED=1
    __INTERNAL=2
    __VIEW_COUNT=0

    def __init__(self, controller, win, plane, num_players, opt):
        self.__opt=opt
        self.__cams=[FollowCam(plane), FixedCam(plane), InternalCam(plane)]
        self.__currentCamera = self.__cams[View.__FIXED]
        self.__controls = controller
        self.__plane_id=plane.getId()
        self.view_id=View.__VIEW_COUNT
        View.__VIEW_COUNT+=1
        self.__win=win
        self.__num_players=num_players
        self.updateDimensions()
        #(self.__xrot, self.__zrot, self.__zoom) = self.__currentCamera.vantage
        self.__screenMessage=''
      
    def updateDimensions(self):
        self.__width=self.__win.width
        self.__height=self.__win.height/self.__num_players
        (self.__xOrig, self.__yOrig) = (0, self.__height*(self.__num_players -1 - self.view_id))
        if self.__num_players==1:
            f_size=16
            width_offset=self.__win.width*0.5
        else:
            f_size=24
            width_offset=self.__win.width*0.75
        self.__label = pyglet.text.Label('bla',
                          font_name='Times New Roman',
                          font_size=f_size,
                          x= - width_offset, y=self.__win.height/2.0,
                          anchor_x='left', anchor_y='top')
        self.__label.color = (0, 0, 0, 255)

    def getAspectRatio(self):
        return self.__width/self.__height

    def getPlaneId(self):
        return self.__plane_id

    def eventCheck(self):
        interesting_events = [Controller.CAM_FIXED, 
                              Controller.CAM_FOLLOW, 
                              Controller.CAM_INTERNAL, 
                              Controller.CAM_X,
                              Controller.CAM_Z,
                              Controller.CAM_ZOOM]
        events = self.__controls.eventCheck(interesting_events)

        if events[Controller.CAM_FOLLOW]!=0:
            self.__currentCamera = self.__cams[View.__FOLLOW]
            self.dispatch_event('view_change', self.view_id)
        if events[Controller.CAM_FIXED]!=0:
            self.__currentCamera = self.__cams[View.__FIXED]
            self.dispatch_event('view_change', self.view_id)
        if events[Controller.CAM_INTERNAL]!=0:
            self.__currentCamera = self.__cams[View.__INTERNAL]
            self.dispatch_event('view_change', self.view_id)
        self.v_type=self.__currentCamera.TYPE
        (xrot, zrot, zoom)=self.__currentCamera.vantage
        zrot += events[Controller.CAM_X]
        xrot += events[Controller.CAM_Z]
        zoom += events[Controller.CAM_ZOOM]
        self.__currentCamera.vantage=(xrot, zrot, zoom)
        self.__controls.clearEvents(interesting_events)

    def activate(self):
        if self.__height==0:
            height=1
        else:
            height=self.__height
        glViewport(self.__xOrig, self.__yOrig, self.__width, height)
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        gluPerspective(70, 1.0*self.__width/height, 0.1, self.__opt.width * 1.2)
        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()
        self.__currentCamera.activate()

    def getPlaneView(self, plane_id):
        if plane_id==self.getPlaneId():
            return self.v_type
        else:
            return EXTERNAL

    def getPos(self):
        return self.__currentCamera.pos

    def getEye(self):
        return self.__currentCamera.eye

    def getZen(self):
        return self.__currentCamera.zen

    def getCamera(self):
        return self.__currentCamera

    def printToScreen(self, message):        
            self.__screenMessage += '[' + message + ']'

    def drawText(self):
            glPushMatrix()
            glTranslatef(-200, 0, -750)
            self.__label.text = self.__screenMessage                
            self.__label.draw()
            glPopMatrix()
            self.__clearText()

    def __clearText(self):
        self.__screenMessage = ''
View.register_event_type('view_change')
