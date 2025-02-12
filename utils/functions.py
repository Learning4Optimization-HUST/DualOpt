import warnings

import torch
import numpy as np
import os
import json
from tqdm import tqdm
from multiprocessing.dummy import Pool as ThreadPool
from multiprocessing import Pool
import torch.nn.functional as F
import math

def load_problem(name):
    from problems import TSP,LOCAL
    problem = {
        'local': LOCAL,
        'tsp': TSP,
    }.get(name, None)
    assert problem is not None, "Currently unsupported problem: {}!".format(name)
    return problem

def solve_gurobi(directory, name, loc, disable_cache=False, timeout=None, gap=None):
    # Lazy import so we do not need to have gurobi installed to run this script
    from problems.tsp.tsp_gurobi import solve_euclidian_tsp as solve_euclidian_tsp_gurobi

    try:
        problem_filename = os.path.join(directory, "{}.gurobi{}{}.pkl".format(
            name, "" if timeout is None else "t{}".format(timeout), "" if gap is None else "gap{}".format(gap)))

        if os.path.isfile(problem_filename) and not disable_cache:
            (cost, tour, duration) = load_dataset(problem_filename)
        else:
            # 0 = start, 1 = end so add depot twice
            start = time.time()
            
            loc.append(loc[int(len(loc)-1)])
            
            cost, tour = solve_euclidian_tsp_gurobi(loc, threads=1, timeout=timeout, gap=gap)
            duration = time.time() - start  # Measure clock time
            
#             save_dataset((cost, tour, duration), problem_filename)

        # First and last node are depot(s), so first node is 2 but should be 1 (as depot is 0) so subtract 1
        total_cost = calc_tsp_length(loc, tour)
        print(total_cost)
        
#         assert abs(total_cost - cost) <= 1e-5, "Cost is incorrect"
        return total_cost, tour, duration

    except Exception as e:
        # For some stupid reason, sometimes OR tools cannot find a feasible solution?
        # By letting it fail we do not get total results, but we dcan retry by the caching mechanism
        print("Exception occured")
        print(e)
        return None
def torch_load_cpu(load_path):
    return torch.load(load_path, map_location=lambda storage, loc: storage)  # Load on CPU


def move_to(var, device):
    if isinstance(var, dict):
        return {k: move_to(v, device) for k, v in var.items()}
    return var.to(device)


def _load_model_file(load_path, model):
    """Loads the model with parameters from the file and returns optimizer state dict if it is in the file"""

    # Load the model parameters from a saved state
    load_optimizer_state_dict = None
    print('  [*] Loading model from {}'.format(load_path))

    load_data = torch.load(
        os.path.join(
            os.getcwd(),
            load_path
        ), map_location=lambda storage, loc: storage)

    if isinstance(load_data, dict):
        load_optimizer_state_dict = load_data.get('optimizer', None)
        load_model_state_dict = load_data.get('model', load_data)
    else:
        load_model_state_dict = load_data.state_dict()

    state_dict = model.state_dict()

    state_dict.update(load_model_state_dict)

    model.load_state_dict(state_dict)

    return model, load_optimizer_state_dict


def load_args(filename):
    with open(filename, 'r') as f:
        args = json.load(f)

    # Backwards compatibility
    if 'data_distribution' not in args:
        args['data_distribution'] = None
        probl, *dist = args['problem'].split("_")
        if probl == "op":
            args['problem'] = probl
            args['data_distribution'] = dist[0]
    return args


def load_model(path, epoch=None,is_local = False,n_points = None):
    from nets.attention_model import AttentionModel
    
    from nets.pointer_network import PointerNetwork

    if os.path.isfile(path):
        model_filename = path
        path = os.path.dirname(model_filename)
    elif os.path.isdir(path):
        if epoch is None:
            epoch = max(
                int(os.path.splitext(filename)[0].split("-")[1])
                for filename in os.listdir(path)
                if os.path.splitext(filename)[1] == '.pt'
            )
        model_filename = os.path.join(path, 'epoch-{}.pt'.format(epoch))
    else:
        assert False, "{} is not a valid directory or file".format(path)
   
    args = load_args(os.path.join(path, 'args.json'))

    
    if is_local:
        from nets.attention_local import AttentionModel
        model= AttentionModel(
        args['embedding_dim'],
        args['hidden_dim'],
        load_problem('local'),
        n_encode_layers=args['n_encode_layers'],
        mask_inner=True,
        mask_logits=True,
        normalization=args['normalization'],
        tanh_clipping=args['tanh_clipping'],
        checkpoint_encoder=args.get('checkpoint_encoder', False),
        shrink_size=args.get('shrink_size', None)
    )
        
    else:
        problem = load_problem(args['problem']) 
        model_class = {
            'attention': AttentionModel,
            'pointer': PointerNetwork
        }.get(args.get('model', 'attention'), None)
        assert model_class is not None, "Unknown model: {}".format(model_class)
    
        model = model_class(
            args['embedding_dim'],
            args['hidden_dim'],
            problem,
            n_encode_layers=args['n_encode_layers'],
            mask_inner=True,
            mask_logits=True,
            normalization=args['normalization'],
            tanh_clipping=args['tanh_clipping'],
            checkpoint_encoder=args.get('checkpoint_encoder', False),
            shrink_size=args.get('shrink_size', None)
        )
    # Overwrite model parameters by parameters to load
    load_data = torch_load_cpu(model_filename)
    model.load_state_dict({**model.state_dict(), **load_data.get('model', {})})

    model, *_ = _load_model_file(model_filename, model)

    model.eval()  # Put in eval mode

    return model, args


def parse_softmax_temperature(raw_temp):
    # Load from file
    if os.path.isfile(raw_temp):
        return np.loadtxt(raw_temp)[-1, 0]
    return float(raw_temp)


def run_all_in_pool(func, directory, dataset, opts, use_multiprocessing=True):
    # # Test
    # res = func((directory, 'test', *dataset[0]))
    # return [res]

    num_cpus = os.cpu_count() if opts.cpus is None else opts.cpus

    w = len(str(len(dataset) - 1))
    offset = getattr(opts, 'offset', None)
    if offset is None:
        offset = 0
    ds = dataset[offset:(offset + opts.n if opts.n is not None else len(dataset))]
    pool_cls = (Pool if use_multiprocessing and num_cpus > 1 else ThreadPool)
    with pool_cls(num_cpus) as pool:
        results = list(tqdm(pool.imap(
            func,
            [
                (
                    directory,
                    str(i + offset).zfill(w),
                    *problem
                )
                for i, problem in enumerate(ds)
            ]
        ), total=len(ds), mininterval=opts.progress_bar_mininterval))

    failed = [str(i + offset) for i, res in enumerate(results) if res is None]
    assert len(failed) == 0, "Some instances failed: {}".format(" ".join(failed))
    return results, num_cpus


def do_batch_rep(v, n):
    if isinstance(v, dict):
        return {k: do_batch_rep(v_, n) for k, v_ in v.items()}
    elif isinstance(v, list):
        return [do_batch_rep(v_, n) for v_ in v]
    elif isinstance(v, tuple):
        return tuple(do_batch_rep(v_, n) for v_ in v)

    return v[None, ...].expand(n, *v.size()).contiguous().view(-1, *v.size()[1:])



def decomposition(seeds, coordinate_dim, revision_len,offset, shift_len):
    # change decomposition point
    
    seeds = torch.cat([seeds[:, shift_len:],seeds[:, :shift_len]],1)

    if offset!=0:
        decomposed_seeds = seeds[:, :-offset]
        offset_seeds = seeds[:,-offset:]
    else:
        decomposed_seeds = seeds
        offset_seeds = None
    # decompose original seeds
    decomposed_seeds = decomposed_seeds.reshape(-1, revision_len, coordinate_dim)
    
    return decomposed_seeds,offset_seeds

def coordinate_transformation(x):
    input = x.clone()
    max_x, indices_max_x = input[:,:,0].max(dim=1) 
    max_y, indices_max_y = input[:,:,1].max(dim=1)
    min_x, indices_min_x = input[:,:,0].min(dim=1)
    min_y, indices_min_y = input[:,:,1].min(dim=1)
    
    diff_x = max_x - min_x
    diff_y = max_y - min_y

    # shift to zero
    input[:, :, 0] -= (min_x).unsqueeze(-1)
    input[:, :, 1] -= (min_y).unsqueeze(-1)
    
    # scale to (0, 1)
    scale_degree = torch.max(diff_x, diff_y)
    scale_degree = scale_degree.view(input.shape[0], 1, 1)
    input /= scale_degree + 1e-10
    return input

def revision(revision_cost_func,reviser, decomposed_seeds, original_subtour, decomposed_pi=None):

    # tour length of segment TSPs
    init_cost = revision_cost_func(decomposed_seeds, original_subtour)
    transform_decomposed_seeds = coordinate_transformation(decomposed_seeds)
    cost_revised1, sub_tour1, cost_revised2, sub_tour2 = reviser(transform_decomposed_seeds, return_pi=True)
    _, better_tour_idx = torch.stack((cost_revised1, cost_revised2)).min(dim=0)
    sub_tour = torch.stack((sub_tour1, sub_tour2))[better_tour_idx, torch.arange(sub_tour1.shape[0])]
    cost_revised, _ = reviser.problem.get_costs(decomposed_seeds, sub_tour)
    reduced_cost = init_cost - cost_revised

    # preserve previous tour if reduced cost is negative
    sub_tour[reduced_cost < 0] = original_subtour
    decomposed_seeds = decomposed_seeds.gather(1, sub_tour.unsqueeze(-1).expand_as(decomposed_seeds))

    if decomposed_pi !=None:
        decomposed_pi = decomposed_pi.gather(1, sub_tour)
        return decomposed_seeds, decomposed_pi
    
    return decomposed_seeds

def LCP_TSP(seeds,cost_func,reviser,revision_len,revision_iter):
        batch_size, num_nodes, coordinate_dim = seeds.shape
        offset = num_nodes % revision_len
        original_subtour = torch.range(0, revision_len - 1, dtype=torch.long).cuda()
        
        for _ in range(revision_iter):
            decomposed_seeds,offset_seed = decomposition(seeds, coordinate_dim
                                                         , revision_len,offset, shift_len=max(1,revision_len//revision_iter))
            decomposed_seeds_revised = revision(cost_func, reviser, decomposed_seeds, original_subtour)

            seeds = decomposed_seeds_revised.reshape(batch_size, -1, coordinate_dim)
            
            if offset_seed is not None:
                seeds = torch.cat([seeds,offset_seed],dim=1)  
         
        return seeds
    
def second_step(seeds, get_cost_func, opts ,revisers):
    """
    :param input: (batch_size, graph_size, node_dim) input node features
    :return:
    """
    cost_original = (seeds[:, 1:] - seeds[:, :-1]).norm(p=2, dim=2).sum(1) + (seeds[:, 0] - seeds[:, -1]).norm(p=2, dim=1)
    if len(revisers) == 0:
        cost_revised = cost_original
    
    if opts.problem =='tsp':
        
        for revision_id in range(len(revisers)):
            seeds = LCP_TSP(seeds, get_cost_func, revisers[revision_id], opts.revision_lens[revision_id], opts.revision_iters[revision_id])
        cost_revised = (seeds[:, 1:] - seeds[:, :-1]).norm(p=2, dim=2).sum(1) + (seeds[:, 0] - seeds[:, -1]).norm(p=2, dim=1)

        return cost_original, cost_revised

    else:

        mincosts, argmincosts = cost.min(0)
        min_tour = pi[argmincosts]
        return pi, mincosts, None






