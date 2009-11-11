from scan import Scan

import unittest
import theano

import random
import numpy.random
from theano.tests  import unittest_tools as utt



def verify_grad(op, pt, n_tests=2, rng=None, eps = None, tol = None, 
                mode = None, cast_to_output_type = False):
    pt = [numpy.array(p) for p in pt]

    _type_tol = dict( float32=1e-2, float64=1e-4)

    if tol is None:
        tol = max(_type_tol[str(p.dtype)] for p in pt)

    if rng is None:
        rng = numpy.random
        utt.seed_rng()
    
    def function(inputs, outputs):
        if mode is None:
            f = theano.function(inputs, outputs, accept_inplace=True)
        else:
            f = theano.function(inputs,outputs,accept_inplace=True, mode=mode)
        return f

    for test_num in xrange(n_tests):
        tensor_pt=[theano.tensor.value(p.copy(),name='input %i'%i) 
                                       for i,p in enumerate(pt)]
    # op outputs
    o_outputs = op(*tensor_pt)
    if not (type(o_outputs) in (list,tuple)):
        o_outputs = [ o_outputs ]
    o_fn = function(tensor_pt, o_outputs)
    o_fn_outs = o_fn(*[p.copy() for p in pt])

    if not type(o_fn_outs) in (list,tuple):
        o_fn_outs = [o_fn_outs]

    random_projection = rng.rand(*o_fn_outs[0].shape)
    if cast_to_output_type:
        random_projection = numpy.array(random_projection, 
                             dtype = o_fn_outs[0].dtype)
    t_r = theano.tensor.as_tensor_variable(random_projection)
    cost = theano.tensor.sum( t_r * o_outputs[0])
    for i, o in enumerate(o_fn_outs[1:] ):
        random_projection = rng.rand(*o.shape)
        if cast_to_output_type:
            random_projection = numpy.array(random_projection,
                                            dtype=o_outputs[i].dtype)
        t_r  = theano.tensor.as_tensor_variable(random_projection)
        cost += theano.tensor.sum( t_r * o_outputs[i])
    cost_fn = function(tensor_pt, cost)
    num_grad = theano.tensor.numeric_grad(cost_fn,[p.copy() for p in pt],eps)
    g_cost = theano.tensor.as_tensor_variable(1.0,name='g_cost')
    if cast_to_output_type:
        g_cost = cast(g_cost, o_output.dtype)
    symbolic_grad = theano.tensor.grad(cost, tensor_pt, g_cost)
    

    grad_fn = function(tensor_pt,symbolic_grad)
    analytic_grad = grad_fn(*[p.copy() for p in pt])
    if not isinstance(analytic_grad, (list,tuple)):
        analytic_grad = [analytic_grad]

    max_err, max_err_pos = num_grad.max_err(analytic_grad)
    if max_err > tol:
        raise Exception(theano.tensor.verify_grad.E_grad, 
                                    (max_err, tol, max_err_pos))



class T_Scan(unittest.TestCase):
    def setUp(self):
        utt.seed_rng()
        x_1 = theano.tensor.dscalar('x_1')
        self.my_f = theano.function([x_1],[x_1]) #dummy function
    
    # Naming convention : 
    #  u_1,u_2,..   -> inputs, arrays to iterate over
    #  x_1,x_2,..   -> outputs at t-1 that are required in the recurrent 
    #                  computation
    #  iu_1,iu_2,.. -> inplace inputs, inputs that are being replaced by 
    #                  outputs during computation
    #  du_1,du_2,.. -> dummy inputs used to do inplace computation, they 
    #                  are not passed to my_f
    #  ix_1,ix_2,.. -> inplace outputs at t-1
    #  x_1_next,..  -> outputs at t
    #  ix_1_next,.. -> inplace outputs at  time t
    #  w_1,w_2,..   -> weights, paramters over which scan does not iterate
    #  my_f         -> compiled function that will be applied recurrently
    #  my_op        -> operator class
    #  final_f      -> compiled function that applies the Scan operation
    #  out_1,..     -> outputs of the Scan operation
    ###################################################################
    def test_numberOfIterableInputs(self):
        def t1():
            my_op = Scan.compiled(self.my_f,-1,1)

        def t2():
            my_op = Scan.compiled(self.my_f,0,1)
        
        self.failUnlessRaises(ValueError,t1)
        self.failUnlessRaises(ValueError,t2)

    ###################################################################
    def test_numberOfOutputs(self):
        def t1():
            my_op = Scan.compiled(self.my_f,1,-1)

        def t2():
            my_op = Scan.compiled(self.my_f,1,0)
        
        self.failUnlessRaises(ValueError,t1)
        self.failUnlessRaises(ValueError,t2)

    #####################################################################
    def test_numberOfInplaceOutputs(self):
        def t1():
            my_op =Scan.compiled(self.my_f,1,1,n_inplace = -1)
        def t2():
            my_op =Scan.compiled(self.my_f,1,1,n_inplace = 2)
        def t3():
            my_op =Scan.compiled(self.my_f,2,1,n_inplace=2)
        def t4():
            my_op =Scan.compiled(self.my_f,1,2,n_inplace=2)
        def t5():
            my_op =Scan.compiled(self.my_f,1,1,n_inplace=1,n_inplace_ignore=2)
        
        self.failUnlessRaises(ValueError,t1)
        self.failUnlessRaises(ValueError,t2)
        self.failUnlessRaises(ValueError,t3)
        self.failUnlessRaises(ValueError,t4)
        self.failUnlessRaises(ValueError,t5)
    #####################################################################
    def test_taps(self):
        def t1():
            my_op = Scan.compiled(self.my_f,1,1, taps={2:[3]})
        def t2():
            my_op = Scan.compiled(self.my_f,1,2, taps={0:[0]})
        def t3():
            my_op = Scan.compiled(self.my_f,1,2, taps={0:[1]})

        self.failUnlessRaises(ValueError,t1)
        self.failUnlessRaises(ValueError,t2)
        self.failUnlessRaises(ValueError,t3)

    #####################################################################
    def test_makeNode(self):
        def t1():
            ######### Test inputs of different lengths
            # define the function that is applied recurrently
            u_1      = theano.tensor.dscalar('u_1')
            u_2      = theano.tensor.dscalar('u_2')
            x_1      = theano.tensor.dscalar('x_1')
            x_1_next = u_1+u_2*x_1
            my_f     = theano.function([u_1,u_2,x_1],[x_1_next])
            # define the function that applies the scan operation
            my_op    = Scan.compiled(my_f,2,1)
            u_1      = theano.tensor.dvector('u_1')
            u_2      = theano.tensor.dvector('u_2')
            x_1      = theano.tensor.dvector('x_1')
            x_1_next = my_op(u_1,u_2,x_1)
            final_f  = theano.function([u_1,u_2,x_1],[x_1_next])

            # test the function final_f
            u_1 = numpy.random.rand(3)
            u_2 = numpy.random.rand(2)
            x_1 = [numpy.random.rand()]
            out = final_f(u_1,u_2,x_1)
    
        def t2():
            ######### Test function does not return correct number of outputs
            # define the function that is applied recurrently
            u_1       = theano.tensor.dscalar('u_1')
            x_1       = theano.tensor.dscalar('x_1')
            x_1_next  = u_1 * x_1
            my_f      = theano.function([u_1,x_1],[x_1_next])
            # define the function that applies the scan operation
            my_op     = Scan.compiled(my_f,1,2)
            u_1       = theano.tensor.dvector('u_1')
            x_1       = theano.tensor.dvector('x_1')
            x_2       = theano.tensor.dvector('x_2')
            x_1_next,x_2_next = my_op(u_1,x_1,x_2)
            final_f   = theano.function([u_1,x_1,x_2],[x_1_next,x_2_next])

            #generate data
            u_1 = numpy.random.rand(3)
            x_1 = [numpy.random.rand()]
            x_2 = [numpy.random.rand()]
            out_1,out_2 = final_f(u_1,x_1,x_2)
 

        self.failUnlessRaises(ValueError,t1)
        self.failUnlessRaises(TypeError,t2)

    
    #####################################################################
    def test_generator(self):
        # compile my_f
        u_1       = theano.tensor.dscalar('u_1') # dummy input, 
                                            # required if no inplace is used!
        x_1       = theano.tensor.dscalar('x_1')
        w_1       = theano.tensor.dscalar('w_1')
        x_1_next  = x_1*w_1
        my_f      = theano.function([u_1,x_1,w_1],[x_1_next])
        # create operation
        my_op     = Scan.compiled(my_f,1,1)
        u_1       = theano.tensor.dvector('u_1') # dummy input, there is no 
                    #inplace, so output will not be put in place of this u_1!
        x_1       = theano.tensor.dvector('x_1')
        w_1       = theano.tensor.dscalar('w_1')
        x_1_next  = my_op(u_1,x_1,w_1)
        final_f   = theano.function([u_1,x_1,w_1],[x_1_next])

        #generate data
        x_1   = numpy.ndarray(3) # dummy input, just tells for how many time 
                               # steps to run recursively
        out_1 = final_f(x_1,[2],2)
        self.failUnless(numpy.all(out_1 == numpy.asarray([4,8,16]))) 


    #####################################################################
    def test_generator_inplace_no_ignore(self):
        # compile my_f
        u_1      = theano.tensor.dscalar('u_1')
        x_1      = theano.tensor.dscalar('x_1')
        w_1      = theano.tensor.dscalar('w_1')
        x_1_next = x_1*w_1
        my_f     = theano.function([u_1,x_1,w_1],[x_1_next])
        # create operation
        my_op    = Scan.compiled(my_f,1,1,n_inplace=1)
        iu_1     = theano.tensor.dvector('iu_1')
        ix_1     = theano.tensor.dvector('ix_1')
        w_1      = theano.tensor.dscalar('w_1')
        ix_1_next= my_op(iu_1,ix_1,w_1)
        final_f  = theano.function([theano.In(iu_1, mutable=True),ix_1,w_1],
                                [ix_1_next], mode='FAST_RUN')

        #generate data
        iu_1  = numpy.ndarray(3)
        out_1 = final_f(iu_1,[2],2)
        # not concretely implemented yet .. 
        self.failUnless(numpy.all(out_1 == numpy.asarray([4,8,16])))
        self.failUnless(numpy.all(out_1 == iu_1))

    #####################################################################
    def test_generator_inplace_no_ignore_2states(self):
        # compile my_f
        u_1      = theano.tensor.dscalar('u_1')
        u_2      = theano.tensor.dscalar('u_2')
        x_1      = theano.tensor.dscalar('x_1')
        x_2      = theano.tensor.dscalar('x_2')
        w_1      = theano.tensor.dscalar('w_1')
        x_1_next = x_1*w_1
        x_2_next = x_2*w_1
        my_f     = theano.function([u_1,u_2,x_1,x_2,w_1],[x_1_next,x_2_next])
        # create operation
        my_op    = Scan.compiled(my_f,2,2,n_inplace=2)
        iu_1     = theano.tensor.dvector('iu_1')
        iu_2     = theano.tensor.dvector('iu_2')
        ix_1     = theano.tensor.dvector('ix_1')
        ix_2     = theano.tensor.dvector('ix_2')
        w_1      = theano.tensor.dscalar('w_1')
        ix_1_next,ix_2_next= my_op(iu_1,iu_2,ix_1,ix_2,w_1)
        final_f  = theano.function([theano.In(iu_1, mutable=True),
                              theano.In(iu_2, mutable=True),ix_1,ix_2,
                              w_1],[ix_1_next,ix_2_next], mode='FAST_RUN')

        #generate data
        iu_1  = numpy.ndarray(3)
        iu_2  = numpy.ndarray(3)
        out_1,out_2 = final_f(iu_1,iu_2,[2],[1],2)
        # not concretely implemented yet .. 
        self.failUnless(numpy.all(out_1 == numpy.asarray([4,8,16])))
        self.failUnless(numpy.all(out_1 == iu_1))
        self.failUnless(numpy.all(out_2 == numpy.asarray([2,4,8])))
        self.failUnless(numpy.all(out_2 == iu_2))

    #######################################################################
    def test_generator_inplace(self):
        #compile my_f
        u_1      = theano.tensor.dscalar('u_1')
        x_1      = theano.tensor.dscalar('x_1')
        x_2      = theano.tensor.dscalar('x_2')
        x_1_next = u_1 + x_1
        x_2_next = x_1 * x_2
        my_f     = theano.function([u_1,x_1,x_2],[x_1_next,x_2_next])
        # create operation
        my_op    = Scan.compiled(my_f,2,2,n_inplace=2,n_inplace_ignore=1)
        du_1     = theano.tensor.dvector('du_1')
        iu_1     = theano.tensor.dvector('iu_1')
        ix_1     = theano.tensor.dvector('ix_1')
        ix_2     = theano.tensor.dvector('ix_2')
        ix_1_next,ix_2_next = my_op(du_1,iu_1,ix_1,ix_2)
        final_f=theano.function([theano.In(du_1, mutable = True),
                                 theano.In(iu_1, mutable = True),
                            ix_1,ix_2],[ix_1_next,ix_2_next],mode='FAST_RUN')
        # generate data
        du_1 = numpy.asarray([0.,0.,0.])
        iu_1 = numpy.asarray([1.,1.,1.])
        ix_1 = [1]
        ix_2 = [1]
        out_1,out_2 = final_f(du_1,iu_1,ix_1,ix_2)
        self.failUnless(numpy.all(out_1 == numpy.asarray([2,3,4])))
        self.failUnless(numpy.all(out_2 == numpy.asarray([1,2,6])))
        self.failUnless(numpy.all(out_1 == du_1))
        self.failUnless(numpy.all(out_2 == iu_1))

    #####################################################################
    def tets_iterateOnlyOverX(self):
        u_1      = theano.tensor.dscalar('u_1')
        x_1      = theano.tensor.dscalar('x_1')
        x_1_next = u_1*x_1
        my_f     = theano.function([u_1,x_1],[x_1_next])
        my_op    = Scan.compiled(my_f,1,1)
        u_1      = theano.tensor.dvector('u_1')
        x_1      = theano.tensor.dvector('x_1')
        x_1_next = my_op(u_1,x_1)
        final_f  = theano.function([x_1,u_1],[x_1_next])
        u_1      = numpy.asarray([2,2,2])
        out_1    = final_f(inp,2)
        self.failUnless(numpy.all(out_1==numpy.asarray([4,8,16])))

    #####################################################################
    def test_iterateOverSeveralInputs(self):

        u_1 = theano.tensor.dscalar('u_1') # input 1
        u_2 = theano.tensor.dscalar('u_2') # input 2
        x_1 = theano.tensor.dscalar('x_1') # output
        x_1_next = (u_1+u_2)*x_1
        my_f  = theano.function([u_1,u_2,x_1],[x_1_next])
        my_op = Scan.compiled(my_f,2,1)
        u_1 = theano.tensor.dvector('u_1')
        u_2 = theano.tensor.dvector('u_2')
        x_1 = theano.tensor.dvector('x_1')
        x_1_next = my_op(u_1,u_2,x_1)
        final_f = theano.function([u_1,u_2,x_1],[x_1_next])
        u_1 = numpy.asarray([1,1,1])
        u_2 = numpy.asarray([1,1,1])
        x_1 = [2]
        out_1 = final_f(u_1,u_2,x_1)
        self.failUnless(numpy.all(out_1==numpy.asarray([4,8,16])))
    
    #####################################################################
    def test_iterateOverSeveralInputsSeveralInplace(self):
        iu_1 = theano.tensor.dscalar('iu_1')
        u_1  = theano.tensor.dscalar('u_1')
        u_2  = theano.tensor.dscalar('u_2')
        u_3  = theano.tensor.dscalar('u_3')
        u_4  = theano.tensor.dscalar('u_4')
        ix_1 = theano.tensor.dscalar('ix_1')
        ix_2 = theano.tensor.dscalar('ix_2')
        x_1  = theano.tensor.dscalar('x_1')
        w_1  = theano.tensor.dscalar('w_1')
        ix_1_next = u_3 + u_4
        ix_2_next = ix_1 + ix_2
        x_1_next  = x_1 + u_3 + u_4 + ix_1 + ix_2
        my_f = theano.function([iu_1,u_1,u_2,u_3,u_4,ix_1,ix_2,x_1,w_1],\
                    [ix_1_next,ix_2_next, x_1_next])
        my_op = Scan.compiled(my_f,6,3, n_inplace=2,\
                                    n_inplace_ignore=1)
        du_1 = theano.tensor.dvector('du_1')
        iu_1 = theano.tensor.dvector('iu_1')
        u_1  = theano.tensor.dvector('u_1')
        u_2  = theano.tensor.dvector('u_2')
        u_3  = theano.tensor.dvector('u_3')
        u_4  = theano.tensor.dvector('u_4')
        x_1  = theano.tensor.dvector('x_1')
        ix_1 = theano.tensor.dvector('ix_1')
        ix_2 = theano.tensor.dvector('ix_2')
        w_1  = theano.tensor.dscalar('w_1')
        [ix_1_next,ix_2_next,x_1_next]= \
            my_op(du_1,iu_1,u_1,u_2,u_3,u_4,x_1,ix_1,ix_2,w_1)
        final_f=theano.function([theano.In(du_1, mutable = True),
                                 theano.In(iu_1, mutable = True),
                                 u_1,u_2,u_3,u_4,ix_1,ix_2,x_1,w_1],
                                 [ix_1_next,ix_2_next,
                                  x_1_next],mode='FAST_RUN')
        #generate data
        du_1 = numpy.asarray([0.,0.,0.])
        iu_1 = numpy.asarray([0.,1.,2.])
        u_1  = numpy.asarray([1.,2.,3.])
        u_2  = numpy.asarray([1.,1.,1.])
        u_3  = numpy.asarray([2.,2.,2.])
        u_4  = numpy.asarray([3.,2.,1.])
        x_1  = [1.]
        ix_1 = [1.]
        ix_2 = [1.]
        w_1  = 2.
        out_1,out_2,out_3 = final_f(du_1,iu_1,u_1,u_2,u_3,u_4,\
                ix_1,ix_2,x_1,w_1)
        self.failUnless(numpy.all(out_3 == numpy.asarray([8.,19.,33.])))
        self.failUnless(numpy.all(out_1 == numpy.asarray([5.,4.,3.])))
        self.failUnless(numpy.all(out_2 == numpy.asarray([2.,7.,11.])))
        self.failUnless(numpy.all(out_1 == du_1))
        self.failUnless(numpy.all(out_2 == iu_1))
   

    #####################################################################
    def test_computeInPlaceArguments(self):
        u_1      = theano.tensor.dscalar('u_1')
        x_1      = theano.tensor.dscalar('x_1')
        w_1      = theano.tensor.dscalar('w_1')
        x_1_next = u_1*w_1+x_1
        my_f     = theano.function([u_1,x_1,theano.In(w_1,update=w_1*2)],
                        [x_1_next])
        my_op = Scan.compiled(my_f,1,1)
        u_1 = theano.tensor.dvector('u_1')
        x_1 = theano.tensor.dvector('x_1')
        w_1 = theano.tensor.dscalar('w_1')
        x_1_next = my_op(u_1,x_1,w_1)
        final_f = theano.function([u_1,x_1,w_1], [x_1_next])
        u_1 = [1.,1.,1.]
        x_1 = [1.]
        w_1 = 1.
        out_1 = final_f(u_1,x_1,w_1)
        self.failUnless(numpy.all(out_1 == numpy.asarray([2,4,8])))


    #####################################################################
    def test_timeTaps(self):
        u_1       = theano.tensor.dscalar('u_1')
        x_1       = theano.tensor.dscalar('x_1')
        x_1_t2    = theano.tensor.dscalar('x_1_t2')
        x_1_t4    = theano.tensor.dscalar('x_1_t4')
        x_1_next  = u_1+x_1+x_1_t2+x_1_t4
        my_f      = theano.function([u_1,x_1,x_1_t2,x_1_t4],[x_1_next])
        my_op     = Scan.compiled(my_f,1,1,taps={0:[2,4]})
        u_1       = theano.tensor.dvector('u_1')
        x_1       = theano.tensor.dvector('x_1')
        x_1_next  = my_op(u_1,x_1)
        final_f   = theano.function([u_1,x_1],[x_1_next])
        u_1       = [1.,1.,1.,1.,1.]
        x_1       = [1.,2.,3.,4.]
        out_1     = final_f(u_1,x_1)
        self.failUnless(numpy.all(out_1==numpy.asarray([9.,16.,29.,50.,89.])))


    #####################################################################
    def test_constructFunction(self):
        u_1      = theano.tensor.dscalar('u_1')
        x_1      = theano.tensor.dscalar('x_1')
        x_1_next = u_1 + x_1
        my_op    = Scan.symbolic(([u_1,x_1],x_1_next),1,1)
        u_1      = theano.tensor.dvector('u_1')
        x_1      = theano.tensor.dvector('x_1')
        x_1_next = my_op(u_1,x_1)
        final_f  = theano.function([u_1,x_1],[x_1_next])
        u_1      = [1.,1.,1.]
        x_1      = [1.]
        out_1    = final_f(u_1,x_1)
        self.failUnless(numpy.all(out_1==numpy.asarray([2.,3.,4.])))

    ######################################################################
    def test_gradOneInputOneOutput(self):
        u_1      = theano.tensor.dscalar('u_1')
        x_1      = theano.tensor.dscalar('x_1')
        x_1_next = u_1*x_1
        my_op    = Scan.symbolic( ([u_1,x_1],x_1_next), 1,1)
        u_1     = [1.,2.,3.]
        x_1     = [1.]

        verify_grad( my_op , [u_1,x_1] )


    #######################################################################
    def test_gradManyInputsManyOutputs(self):
        u_1      = theano.tensor.dscalar('u_1')
        u_2      = theano.tensor.dscalar('u_2')
        x_1      = theano.tensor.dscalar('x_1')
        x_2      = theano.tensor.dscalar('x_2')
        x_1_next = x_1*u_1+x_2
        x_2_next = x_2*u_2+x_1
        my_op    = Scan.symbolic( ([u_1,u_2,x_1,x_2],
                                   [x_1_next,x_2_next]),
                          2,2)
        u_1  = [1.,.2,3.]
        u_2  = [1.5,1.25,.35]
        x_1  = [.5]
        x_2  = [.65]

        verify_grad(my_op, [u_1,u_2,x_1,x_2])


    ######################################################################
    def test_gradTimeTaps(self):
        u_1       = theano.tensor.dscalar('u_1')
        x_1       = theano.tensor.dscalar('x_1')
        x_1_t_2   = theano.tensor.dscalar('x_1_t_2')

        x_1_next = x_1_t_2*x_1*u_1
        my_op    = Scan.symbolic( ([u_1,x_1,x_1_t_2],
                                   [x_1_next]),
                        1,1,taps={0:[2]})
        u_1 = [1.,2.,3.,4.]
        x_1 = [2.,3.]

        verify_grad(my_op, [u_1,x_1])

    #######################################################################
    def test_gradManyInputsManyOutputsTimeTaps(self):
        u_1   = theano.tensor.dscalar('u_1')
        u_2   = theano.tensor.dscalar('u_2')
        x_1   = theano.tensor.dscalar('x_1')
        x_1_2 = theano.tensor.dscalar('x_1_2')
        x_2   = theano.tensor.dscalar('x_2')
        x_2_2 = theano.tensor.dscalar('x_2_2')
        x_1_n = x_1*x_2_2 + u_1*x_1_2
        x_2_n = x_2*x_1_2 + u_2*x_2_2
        my_op = Scan.symbolic(([u_1,u_2,x_1,x_1_2,
                                x_2,x_2_2],[x_1_n,
                                x_2_n]),2,2,taps=
                                {0:[2],1:[2]})

        u_1 = [1.,2.,3.,4.]
        u_2 = [3.,2.,4.,1.]
        x_1 = [0.1,0.2]
        x_2 = [1.5,3.5]

        verify_grad(my_op, [u_1,u_2,x_1,x_2])

if __name__ == '__main__':
    unittest.main()
