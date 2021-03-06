'''
The function library

Modification log:

7/7/2016 - add a YTM to price function for ZCB

6/14/2016 - fix an error in getParRate

6/13/2016 - generalized the linear interpolation methods

6/12/2016 - generalized the bootstraping method, generalized the Nelson-Siegel,
            fixed minor bugs

'''

import pandas as pd
import numpy as np
from numpy.linalg import inv
from scipy.optimize import minimize



def bootstrapSpotToZ( RawRate, RawT, T, t = 0 , n = 1, isCts = False):
    '''
    WARNING 6/12/2016: this function is replaced by bootstrapXToY

    Bootstrap from Spot to discount rate
    RawSpot is an array of spot rates with corresponding RawT, i.e. Maturities
    '''
    rate = np.array([RawRate[RawT >= x].values.tolist()[0] for x in T]) # this does not prevent error
    return spotToZ(rate, T, t = t, n = n, isCts = isCts)



def bootstrapXToY( RawRate, RawT, T, XToY, BSMethod = lambda x,y,z : \
                    linInter(x,y,z), t = 0 , n = 1, isCts = False):
    '''
    WARNING 6/12/2016: currently this function is a generalization of bootstrapSpotToZ,
    which also fix the error issue

    6/12/2016: now it supports different BS methods (i.e., linear, step, spline...)

    bootstrap from X to Y (e.g., Spot to Z; Z to Spot; Spot to Spot; Z to Z...)
    RawRate & RawT are the discrete data points for bootstraping, which HAVE to have the same size.
    XToY can be any metrix exchange function with parameter( X, T, t, n = 0, isCts = False )
    e.g. if RawRate is Spot rate, XToY could be spotToZ
    '''
    BSRate = np.array([BSMethod(RawRate, RawT, x) for x in T]) # get rate from any BS methods
    return XToY(BSRate, T, t = t, n = n, isCts = isCts)



def linInter(RawRate, RawT, T_):
    '''
    WARNING 6/13/2016: T_ is a numeric number. When T_ > max(RawT), return 'nan'
    when T_ < min(RawT), use linear interpolation instead
    (would return 'nan' before the change)
    '''
    if T_ > RawT.max(): # out-bound case
        return float('nan')
    elif (T_ > 0) and ( T_ < RawT.min() ): #low_bound base
        return RawRate[0]

    # if in between...
    try:
        right_T = RawT[RawT >= T_ ].values.tolist()[0]
        left_T = RawT[RawT < T_ ].values.tolist()[-1]
        right_rate = RawRate[RawT >= T_ ].values.tolist()[0]
        left_rate = RawRate[RawT < T_ ].values.tolist()[-1]
        return left_rate + (right_rate - left_rate) * ( T_ - left_T) / (right_T - left_T)
    except:
        return float('nan')



def stepInter(RawRate, RawT, T_ ):
    '''
    regular step interpolation
    '''
    try:
        return RawRate[RawT >= T_ ].values.tolist()[0]
    except:
        return float('nan')



def priceToSpotCts (price, T, par = 100):
    '''
    WARNING 6/12/2016: this function only works when the
    bond is a ZERO-coupon bond. More feature TBA

    transfer price to continuous spot rate
    '''
    return np.log( par / price ) / T


def ctsToDiscrete(cts, n = 1):
    '''
    transfer cts componding to any discrete componding, where n = frequency
    '''
    return n * ( np.exp( cts / n ) - 1 )


def zcbYTMtoPrice(ytm, T, par = 100, t = 0, n = 1, isCts = False):
    '''
    calculate the price of a ZCB given maturity in years and YTM
    '''
    return spotToZ(ytm, T, t = t, n = n, isCts = isCts) * par

def calAnnuityPayment(T, r, par = 100, n = 1, isCts = False):
    '''
    calculate each payment of a self-amortization loan with equal payment
    the return is a tuple of
    (annuity, priciple payments, initerest payments)
    '''
    if (T < 1./n):
        raise Exception('Input period T={}, smaller than smallest payment step={}'.format(T,n))

    N = int(T*n)
    each_pay_ = par / spotToZ(r, np.arange(1./n, T+1./n, 1./n), n = n, isCts = isCts).sum()

    principle_ = np.repeat(each_pay_, N)
    interest_ = np.zeros(N)
    for t_ in range(N):
        interest_[t_] = par * r/n
        principle_[t_] = each_pay_ - interest_[t_]
        par -= principle_[t_]

    return (each_pay_, principle_, interest_)

def calAnnuityValue(T, r, payment, n = 1, isCts = False):
    return spotToZ(r, np.arange(1./n, T+1./n, 1./n), n = n, isCts = isCts).sum() * payment



def spotToZ(rate, T, t = 0, n = 1, isCts = False):
    '''
    transfer the spot rate to discount rate
    '''

    if isCts:  ## if continuous
        #result =  np.exp(- np.multiply(rate,(T - t)))
        result = np.exp(-rate*(T-t))    #if this causes error, switch to the line above
    else:      ## if descrete
        result = np.power((1 + rate / n),(-n*(T - t)))
    return result


def zToSpot(Z, T, t = 0, n = 1, isCts = False):
    '''
    transfer the discount rate to spot rate
    '''
    if isCts: ## if continuous
        result = -np.log(Z) / (T - t)
    else:     ## if descrete
        result = n * (np.power(Z, -1./(n*(T - t))) - 1)
    #result[T==t] = 0 # edge case when T = t, rate = 0
    return result


def ZToCtsFwd(T1, T2, getZ, t = 0):
    '''
    WARNING 6/12/2016: ideally, we want to support any function from spot metric to fwd metric
    get the length-year forward rates from a specific getZ(T, t) function
    '''
    return np.log(getZ(T1, t)/getZ(T2, t))/(T2 - T1)


def getParRate (T, getZ, freq, t = 0, T_fwd = 0 ):
    '''
    WARNING 6/14/2016: genalized the return function

    WARNING 6/12/2016: this function is not bug-free. not too sure about
                       the N-year forward par yield part

    getZ is a function that return the discount rate when pass in a maturity date.
    getParRate can also calculate the Par yield T_fwd-year forward
    '''
    if (type(T)==int or type(T)== float):
        T = np.array([T])


    n = np.ceil( np.multiply(freq ,T- T_fwd) - t ) # how may coupon payment do we pay
                                                   # we use the ceiling function to make sure the coupon
                                                   # is always paid at T
    n[ n < 0 ] = 0

    coupon_date = [ x[0] - (np.arange(1, x[1]+1)-1)/2.0 for x in zip(T, n)]

    #print(n, coupon_date)
    return freq * (1 - getZ(T)/getZ(np.array([T_fwd]))) / \
            [(getZ(x)/getZ(np.array([T_fwd]))).sum() for x in coupon_date]

def getCBPrice( T, c, getZ, freq = 2, par = 100):
    '''
    get the price of a coupon bond, assume t=0
    c is the coupon rate
    '''
    coupon_date = np.linspace(1./freq,T,T*freq) ## e.g. [0.5,1,...,T-0.5,T]
    #print(coupon_date)
    cash_flow = np.repeat(c*par/freq, len(coupon_date))
    cash_flow[-1] += par

    return (getZ(coupon_date)*cash_flow).sum()


class OLS:
    '''
    DIY OSL function
    '''
    def __init__(self, X, y):
        self.X = X
        self.y = y
        self.beta = np.dot(inv(np.dot(pd.DataFrame.transpose(X),X)), np.dot(pd.DataFrame.transpose(X),y))
        self.reg_y = np.dot(X,self.beta)



'''
HW 1-realted functions below:
- five-factor discount function
- five-factor model basis generation
- Nelson-Siegel (4 or 5-parameter)
- Svensson (6-parameter)
'''

def fiveFactorDisc( beta, X ):
    '''
    WARNING 6/12/2016: this function only support when t = 0

    the discount function in Q8
    the retun value is be Z(0, X)
    '''
    return np.exp(np.dot( power_5(X) ,beta))

def power_5(data):
    '''
    Tailored function for Q8 to generate the basis vector
    '''
    if (np.shape(data) == ()): # dealing with edge case, when data is not a integer
        data = np.asarray([data])
    return pd.DataFrame({'T' :data,
                  'T^2': np.power(data,2),
                  'T^3': np.power(data,3),
                  'T^4': np.power(data,4),
                  'T^5': np.power(data,5) })



def NelsonSiegel ( T, beta ):
    '''
    WARNING 6/12/2016: this function only support when t = 0

    spot rate version of the 4 or 5-parameter NS model,
    when  beta is a 5x1 array: [b0, b1, b2, tao1, tao2]
    when  beta is a 4x1 array: [b0, b1, b2, tao1]
    '''
    if beta.size == 5:
        return (beta[0] + beta[1]*(1-np.exp(-T/beta[3])) / (T / beta[3]) +
                beta[2] * ( (1-np.exp(-T/beta[4])) / (T / beta[4]) - np.exp(-T/beta[4]) ))
    else:
        return (beta[0] + beta[1]*(1-np.exp(-T/beta[3])) / (T / beta[3]) +
                beta[2] * ( (1-np.exp(-T/beta[3])) / (T / beta[3]) - np.exp(-T/beta[3]) ))


def Svensson ( T, beta ):
    '''
    WARNING 6/12/2016: this function only support when t = 0

    spot rate version of the 6-parameter Svensson model,
    where beta is a 6x1 array: [b0, b1, b2, b3, tao1, tao2]
    '''
    return (beta[0] + beta[1]*(1-np.exp(-T/beta[4])) / (T / beta[4]) +
            beta[2] * ( (1-np.exp(-T/beta[4])) / (T / beta[4]) - np.exp(-T/beta[4]) ) +
            beta[3] * ( (1-np.exp(-T/beta[5])) / (T / beta[5]) - np.exp(-T/beta[5]) ) )


'''
Optimization-related functions below
'''
# assume a regular RMSE penalty function with
def penaltyFun(x, y,  fun , beta, w = 1,):
    return np.multiply(np.power( (y - fun( x , beta)) , 2 ) , w).sum()

# a wrapper used for minimizing beta's
def penaltyFun_wrapper(x, y, fun, w = 1):
    return lambda beta: penaltyFun(x, y, fun , beta, w = w )


'''
WARNING 6/14/2016: this is not be bug-free, somehow RMSE = 0??!!
'''
def opt_selection( beta_size, minimized, penalty, n = 25 ):
    betas = np.random.rand(n,beta_size) + 3
    results = [ minimized(y).x for y in betas]
    RMSE = [penalty(x) for x in results]
    RMSE[RMSE==0] = 1 # current way of dealing with bug...
    return results[ np.argmin(RMSE)]
