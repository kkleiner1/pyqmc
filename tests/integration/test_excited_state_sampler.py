
#from pyscf import lib, gto, scf
#import pyscf.pbc
import numpy as np
from pyscf.fci.addons import overlap
import pyqmc.api as pyq
import pyqmc.accumulators
from rich import print
from pyqmc.optimize_excited_states import sample_overlap_worker,average, collect_terms, objective_function_derivative, correlated_sampling



def dnttest_excited_state(H2_casci):

    mol, mf, mc = H2_casci

    ci_energies= mc.e_tot
    import copy
    mc1 = copy.copy(mc)
    mc2 = copy.copy(mc)
    mc1.ci = mc.ci[0]
    mc2.ci = (mc.ci[0]+mc.ci[1])/np.sqrt(2)

    wf1, to_opt1 = pyq.generate_slater(mol, mf,mc=mc1, optimize_determinants=True)
    wf2, to_opt2 = pyq.generate_slater(mol, mf, mc=mc2, optimize_determinants=True)
    for to_opt in [to_opt1, to_opt2]:
        to_opt['det_coeff'] = np.ones_like(to_opt['det_coeff'],dtype=bool)

    transform1 = pyqmc.accumulators.LinearTransform(wf1.parameters,to_opt1)
    transform2 = pyqmc.accumulators.LinearTransform(wf2.parameters,to_opt2)
    configs = pyq.initial_guess(mol, 1000)
    _, configs = pyq.vmc(wf1, configs)
    energy =pyq.EnergyAccumulator(mol)
    data_weighted, data_unweighted, configs = sample_overlap_worker([wf1,wf2],configs, energy, [transform1,transform2], nsteps=40, nblocks=20)
    avg, error = average(data_weighted, data_unweighted)
    print(avg, error)
    terms = collect_terms(avg,error)
    derivative = objective_function_derivative(terms,1.0, norm_relative_penalty=1.0)
    print('condition', terms['condition'])
    print('dp', avg['dpidpj'], avg['dppsi'])
    derivative_conditioned = [d/np.sqrt(condition.diagonal()) for d, condition in zip(derivative,terms['condition'])]
    #print('derivative', derivative)
    #print('conditioned derivative',derivative_conditioned)
    #print(data_unweighted)
    ref_energy1 = 0.5*(ci_energies[0] + ci_energies[1])
    assert abs(avg['total'][1] - ref_energy1) < 3*error['total'][1]

    overlap_tolerance = 0.02# magic number..be careful.

    norm = [np.sum(np.abs(m.ci)**2) for m in [mc1,mc2]]
    norm_ref = norm
    
    assert np.all( np.abs(norm_ref - terms['norm']) < overlap_tolerance) 

    norm_derivative_ref = 2*np.real(mc2.ci).flatten() 
    print('norm derivative', norm_derivative_ref, terms['dp_norm'][1])

    assert np.all(np.abs(norm_derivative_ref - terms['dp_norm'][1])<overlap_tolerance)


    overlap_ref = np.sum(mc1.ci*mc2.ci) 
    print('overlap test', overlap_ref, terms['overlap'][0,1])
    assert abs(overlap_ref - terms['overlap'][0,1]) < overlap_tolerance

    overlap_derivative_ref = (mc1.ci.flatten() - 0.5*overlap_ref * norm_derivative_ref) 
    print("overlap_derivative", overlap_derivative_ref, terms['dp_overlap'][1][0,1])
    assert np.all( np.abs(overlap_derivative_ref - terms['dp_overlap'][1][0,1]) < overlap_tolerance)

    mc3 = copy.copy(mc)
    mc3.ci = mc.ci[1]


def test_correlated_sampling(H2_casci):

    mol, mf, mc = H2_casci

    ci_energies= mc.e_tot
    import copy
    mc1 = copy.copy(mc)
    mc2 = copy.copy(mc)
    mc1.ci = mc.ci[0]
    mc2.ci = mc.ci[1]

    wf1, to_opt1 = pyq.generate_slater(mol, mf,mc=mc1, optimize_determinants=True)
    wf2, to_opt2 = pyq.generate_slater(mol, mf, mc=mc2, optimize_determinants=True)
    for to_opt in [to_opt1, to_opt2]:
        to_opt['det_coeff'] = np.ones_like(to_opt['det_coeff'],dtype=bool)

    transform1 = pyqmc.accumulators.LinearTransform(wf1.parameters,to_opt1)
    transform2 = pyqmc.accumulators.LinearTransform(wf2.parameters,to_opt2)
    configs = pyq.initial_guess(mol, 1000)
    _, configs = pyq.vmc(wf1, configs)
    energy =pyq.EnergyAccumulator(mol)
    data_weighted, data_unweighted, configs = sample_overlap_worker([wf1,wf2],configs, energy, [transform1,transform2], nsteps=10, nblocks=10)

    parameters1 = transform1.serialize_parameters(wf1.parameters)
    parameters2 = transform1.serialize_parameters(wf2.parameters)
    sample_parameters = []
    energies_reference = []
    overlap_reference = []
    for theta in np.linspace(0,np.pi/2, 4):
        a = np.cos(theta)
        b = np.sin(theta)
        sample_parameters.append([a*parameters1 + b*parameters2, a*parameters1 - b*parameters2])
        energies_reference.append([a**2*ci_energies[0] + b**2*ci_energies[1]]*2)
        overlap_reference.append([[1.0, a**2-b**2], [a**2-b**2,1.0]]  )
    energies_reference=np.asarray(energies_reference)
    overlap_reference=np.asarray(overlap_reference)
    correlated_results = correlated_sampling([wf1,wf2], configs,energy, [transform1,transform2], sample_parameters )
    energy_sample = correlated_results['energy']/correlated_results['weight_energy']
    print('energy reference',energies_reference)
    print('energy sample', energy_sample)

    assert np.all(np.abs(energy_sample - energies_reference) < 0.1)

    print('overlap sample', correlated_results['overlap'])

    print('overlap reference', overlap_reference)
    assert np.all(np.abs(correlated_results['overlap']-overlap_reference)<0.1)
