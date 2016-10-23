import math
import sys
import time

import numpy as np
import pyglet
from sklearn import linear_model
from matplotlib.legend_handler import HandlerLine2D
import matplotlib.pyplot as plt
import random

import Arm
import Ball

yf = 400.0
total_steps = 200
friction = 0.3 #value between 0 and 1
pi = math.pi
mode = ""

def bezier(p, n):
    t = np.linspace(0, 1, n)
    return p[0] * (1 - t)**3 + p[1] * (1 - t)**2 * t*3 + p[2] * (1 - t) * (t**2) * 3 + p[3] * (t**3)

def calc_steps_linear(q0,qf):
    trajectory_theta1 = np.linspace(q0[0], qf[0], num=total_steps, endpoint=False)
    trajectory_theta2 = np.linspace(q0[1], qf[1], num=total_steps, endpoint=False)

    return trajectory_theta1,trajectory_theta2

def calc_steps_exponential(q0,qf):
    base_traj = 2.0**(np.linspace(0, 1, num=total_steps, endpoint=False))

    #print base_traj

    normalized_traj = (base_traj - min(base_traj)) / (max(base_traj) - min(base_traj))
    trajectory_theta1 = normalized_traj * (qf[0] - q0[0]) + q0[0]
    trajectory_theta2 = normalized_traj * (qf[1] - q0[1]) + q0[1]

    return trajectory_theta1,trajectory_theta2

def calc_steps_cubic(q0,qf):
    base_traj = np.linspace(-1, 0, num=total_steps, endpoint=False) ** 3

    normalized_traj = (base_traj - min(base_traj)) / (max(base_traj) - min(base_traj))
    trajectory_theta1 = normalized_traj * (qf[0] - q0[0]) + q0[0]
    trajectory_theta2 = normalized_traj * (qf[1] - q0[1]) + q0[1]

    return trajectory_theta1,trajectory_theta2


def calc_steps_sigmoid(q0, qf):

    temperature = 5.0

    tmp1 = math.e ** (np.linspace(-1, 1, total_steps))
    tmp2 = tmp1 ** (-temperature)
    base_traj = 1. / (1 + tmp2)

    normalized_traj = (base_traj - min(base_traj)) / (max(base_traj) - min(base_traj))

    trajectory_theta1 = normalized_traj * (qf[0]- q0[0]) + q0[0]
    trajectory_theta2 = normalized_traj * (qf[1] - q0[1]) + q0[1]

    return trajectory_theta1, trajectory_theta2

def calc_steps_bezier(q0, qf):
    normalized_traj = bezier([0,0.7,0.3,1], total_steps)
    trajectory_theta1 = normalized_traj * (qf[0] - q0[0]) + q0[0]
    trajectory_theta2 = normalized_traj * (qf[1] - q0[1]) + q0[1]

    return trajectory_theta1, trajectory_theta2

def calc_steps_mixed(q0,qf):
    trajectory_theta1 = calc_steps_bezier(q0,qf)[0]
    trajectory_theta2 = calc_steps_sigmoid(q0,qf)[1]

    return trajectory_theta1,trajectory_theta2

def convert_deltas(v):
    deltas = []
    deltas.append(v[0])

    for i in range(1,len(v)):
        deltas.append(v[i]-v[i-1])

    return deltas

def convert_trajectory(v,init):
    trajectory = []
    trajectory.append(init)

    for i in range(0,len(v)):
        trajectory.append(v[i]+trajectory[-1])

    return trajectory


def get_joint_positions():
    """This method finds the (x,y) coordinates of each joint"""

    x = np.array([0,
                  arm.L[0] * np.cos(arm.q[0]),
                  arm.L[0] * np.cos(arm.q[0]) + arm.L[1] * np.cos(arm.q[0] + arm.q[1]),
                  arm.L[0] * np.cos(arm.q[0]) + arm.L[1] * np.cos(arm.q[0] + arm.q[1]) +
                  arm.L[2] * np.cos(np.sum(arm.q))]) + window.width / 2

    y = np.array([0,
                  arm.L[0] * np.sin(arm.q[0]),
                  arm.L[0] * np.sin(arm.q[0]) + arm.L[1] * np.sin(arm.q[0] + arm.q[1]),
                  arm.L[0] * np.sin(arm.q[0]) + arm.L[1] * np.sin(arm.q[0] + arm.q[1]) +
                  arm.L[2] * np.sin(np.sum(arm.q))])

    return np.array([x, y]).astype('int')

def calculate_pesos(first,second):
    regr_first = linear_model.LinearRegression(fit_intercept=False)
    regr_second = linear_model.LinearRegression(fit_intercept=False)

    steps_matrix = np.matrix([[1 for t in range(total_steps-1)],
                              [np.sin(pi*t/200) for t in range(total_steps-1)],[np.cos(pi*t/200) for t in range(total_steps-1)],
                              [np.sin(pi*t*2/200) for t in range(total_steps-1)],[np.cos(pi*t*2/200) for t in range(total_steps-1)],
                              [np.sin(pi*t*3/200) for t in range(total_steps-1)],[np.cos(pi*t*3/200) for t in range(total_steps-1)]]).T

    regr_first.fit(steps_matrix,first)
    regr_second.fit(steps_matrix,second)

    return regr_first.coef_,regr_second.coef_


def angles_function(t,mode):

    if(mode == "array_angles"):
        #array of angles
        first_joint = pesos_first[t]
        second_joint = pesos_second[t]
        return [first_joint,second_joint,0.0]

    elif(mode == "array_deltas"):
        #array of deltas
        window.last_first = window.last_first + pesos_first[t]
        window.last_second = window.last_second + pesos_second[t]
        return [window.last_first,window.last_second,0.0]

    elif(mode == "weights_deltas"):
        #with regression and deltas
        window.last_first = window.last_first + pesos_first[0] + \
                            pesos_first[1] * np.sin(pi*t/200) + pesos_first[2] * np.cos(pi*t/200) + \
                            pesos_first[3] * np.sin(pi*t*2/200) + pesos_first[4] * np.cos(pi*t*2/200) + \
                            pesos_first[5] * np.sin(pi*t*3/200) + pesos_first[6] * np.cos(pi*t*3/200)
        window.last_second =  window.last_second + pesos_second[0] + \
                              pesos_second[1] * np.sin(pi*t/200) + pesos_second[1] * np.cos(pi*t/200) + \
                              pesos_second[2] * np.sin(pi*t*2/200) + pesos_second[2] * np.cos(pi*t*2/200) + \
                              pesos_second[3] * np.sin(pi*t*3/200) + pesos_second[3] * np.cos(pi*t*3/200)
        return [window.last_first, window.last_second, 0.0]

    elif(mode == "weights_angles"):
        # with regression and angles
        first_joint = pesos_first[0] + \
                            pesos_first[1] * np.sin(pi * t / 200) + pesos_first[2] * np.cos(pi * t / 200) + \
                            pesos_first[3] * np.sin(pi * t * 2 / 200) + pesos_first[4] * np.cos(pi * t * 2 / 200) + \
                            pesos_first[5] * np.sin(pi * t * 3 / 200) + pesos_first[6] * np.cos(pi * t * 3 / 200)
        second_joint = pesos_second[0] + \
                             pesos_second[1] * np.sin(pi * t / 200) + pesos_second[2] * np.cos(pi * t / 200) + \
                             pesos_second[3] * np.sin(pi * t * 2 / 200) + pesos_second[4] * np.cos(pi * t * 2 / 200) + \
                             pesos_second[5] * np.sin(pi * t * 3 / 200) + pesos_second[6] * np.cos(pi * t * 3 / 200)
        return [first_joint, second_joint, 0.0]


def update(dt):
    label.text = '(x,y) = (%.3f, %.3f)' % (ball.x, ball.y)
    window.traj_theta1.append(arm.q[0])
    window.traj_theta2.append(arm.q[1])
    arm.q = angles_function(window.step,mode)
    window.step = window.step + 1
    window.jps = get_joint_positions()  # get new joint (x,y) positions
    label.text = 'ball = (%.3f, %.3f)' % (ball.x, ball.y)
    ball.update(total_steps)

class Simulation(pyglet.window.Window):
    def __init__(self):

        #push the handlers
        #self.push_handlers(EventHandler(self))

        pyglet.window.Window.__init__(self, 1000, 600)

        pyglet.clock.schedule_interval(update, 1/60.0)

        self.step = 0

        self.last_first = 0.0
        self.last_second = 0.0

        self.traj_theta1 = []
        self.traj_theta2 = []

    def set_jps(self):
        self.jps = get_joint_positions()  # get new joint (x,y) positions

    def on_draw(self):
        self.clear()
        if(self.step == 199):
            arm_xy = arm.get_xy(arm.q)
            arm_xy = (arm_xy[0] + (window.width / 2), arm_xy[1])
            ball_xy = [ball.xf,ball.yf]
            error = np.sqrt((np.array(ball_xy) - np.array(arm_xy)) ** 2)
            print error
        label.draw()
        pyglet.graphics.draw(4, pyglet.gl.GL_QUADS,
                               ('v2f', (ball.x - 10, ball.y - 10,
                                        ball.x + 10, ball.y - 10,
                                        ball.x + 10, ball.y + 10,
                                        ball.x - 10, ball.y + 10)),
                                ('c3B', (255, 0, 0,
                                         255, 0, 0,
                                         255, 0, 0,
                                         255, 0, 0)))

        pyglet.graphics.draw(2, pyglet.gl.GL_LINES, ('v2i',
                                                     (self.width // 2 , self.height,
                                                      self.width // 2, 0)),
                                                    ('c3B', (0, 0, 255,
                                                             0, 0, 255)))

        pyglet.graphics.draw(2, pyglet.gl.GL_LINES, ('v2f',
                                                     (ball.x0, ball.y0,
                                                      ball.xf, ball.yf)),
                                                    ('c3B', (0, 255, 0,
                                                             0, 255, 0)))
        for i in range(3):
            pyglet.graphics.draw(2, pyglet.gl.GL_LINES, ('v2i',
                                                         (self.jps[0][i], self.jps[1][i],
                                                          self.jps[0][i + 1], self.jps[1][i + 1])))

        if(self.step == 199):
            plt.figure(1)
            plt.subplot(211)
            line1, = plt.plot(trajectory_theta1,color='green',label='Expected')
            line2, = plt.plot(self.traj_theta1,color='blue',label='Real')
            plt.legend(handler_map={line1: HandlerLine2D(numpoints=4)}, loc=4)
            plt.title("Real x Expected Theta1")
            plt.ylabel("Angle")

            plt.subplot(212)
            line1, = plt.plot(trajectory_theta2, color='green', label='Expected')
            line2, = plt.plot(self.traj_theta2, color='blue', label='Real')
            plt.legend(handler_map={line1: HandlerLine2D(numpoints=4)}, loc=4)
            plt.title("Real x Expected Theta2")
            plt.xlabel("Step")
            plt.ylabel("Angle")

            plt.show()

            sys.exit()

    '''def on_mouse_motion(self,x, y, dx, dy):
        # call the inverse kinematics function of the arm
        # to find the joint angles optimal for pointing at
        # this position of the mouse
        label.text = '(x,y) = (%.3f, %.3f)' % (x, y)
        arm.q = arm.inv_kin([x - self.width / 2, y])  # get new arm angles
        window.jps = get_joint_positions()  # get new joint (x,y) positions'''


# create an instance of the arm
arm = Arm.Arm3Link(L=np.array([400, 200, 0]))

window = Simulation()
window.set_jps()

# create an instance of the ball
ball = Ball.Ball(float(window.width / 2), float(window.height), math.radians(-60), yf)

distance = math.hypot((ball.xf - (window.width / 2)), (ball.yf - 0))

if distance > arm.reach:
    print "NAO VAI ALCANCAR!"
    raise

label = pyglet.text.Label('Mouse (x,y)', font_name='Times New Roman',
                                  font_size=36, x=window.width // 2, y=window.height // 2,
                                  anchor_x='center', anchor_y='center')

#initial configuration of the arm
q0 = arm.q

#calculate final angles
qf = arm.inv_kin([ball.xf - (window.width / 2), ball.yf])

#how much each joint need to move each step
#trajectory_theta1,trajectory_theta2 = calc_steps_linear(q0,qf)
#trajectory_theta1,trajectory_theta2 = calc_steps_exponential(q0,qf)
#trajectory_theta1,trajectory_theta2 = calc_steps_cubic(q0,qf)
#trajectory_theta1,trajectory_theta2 = calc_steps_sigmoid(q0,qf)
#trajectory_theta1,trajectory_theta2 = calc_steps_bezier(q0,qf)
trajectory_theta1,trajectory_theta2 = calc_steps_mixed(q0,qf)

#first position
window.last_first = trajectory_theta1[0]
window.last_second = trajectory_theta2[0]

#calculate weights that predict the trajectory without friction
pesos_trajectory_without_friction_first,pesos_trajectory_without_friction_second = calculate_pesos(trajectory_theta1[1:],trajectory_theta2[1:])

#convert the trajectory to deltas
deltas_theta1,deltas_theta2 = convert_deltas(trajectory_theta1),convert_deltas(trajectory_theta2)

#calculate weights that predict the deltas without friction
pesos_without_friction_first,pesos_without_friction_second = calculate_pesos(deltas_theta1[1:],deltas_theta2[1:])

#friction applied in the deltas
deltas_friction_theta1 = [p*(1.0 - friction) for p in deltas_theta1[1:]]
deltas_friction_theta2 = [p*(1.0 - friction) for p in deltas_theta2[1:]]

#calculate weights that predict the deltas with friction
pesos_with_friction_first,pesos_with_friction_second = calculate_pesos(deltas_friction_theta1,deltas_friction_theta2)

#convert the frictioned deltas to a frictioned trajectory
trajectory_friction_theta1, trajectory_friction_theta2 = convert_trajectory(deltas_friction_theta1,trajectory_theta1[0]),convert_trajectory(deltas_friction_theta2,trajectory_theta2[0])

#calculate weights that predict the trajectory with friction
pesos_trajectory_with_friction_first,pesos_trajectory_with_friction_second = calculate_pesos(trajectory_friction_theta1[1:],trajectory_friction_theta2[1:])

#define what weights will be used
pesos_first, pesos_second = pesos_trajectory_with_friction_first,pesos_trajectory_with_friction_second
mode = "weights_angles"


pyglet.app.run()
