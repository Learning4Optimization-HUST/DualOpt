# DualOpt

This is the implementation of our work, *DualOpt: A Dual Divide-and-Optimize Algorithm for the Large-scale Traveling
Salesman Problem* (AAAI 2025)

https://arxiv.org/abs/2501.08565

## Operating System

Currently only Linux system is supported.

## Dependencies

show in requirements.txt

- install LKH-3

  ```
  wget http://akira.ruc.dk/~keld/research/LKH-3/LKH-3.0.7.tgz
  tar xvfz LKH-3.0.7.tgz
  cd LKH-3.0.7
  make
  ```

- requirements.txt

  ```
  pip install -r requirements.txt
  ```

Note that [LKH-3](http://akira.ruc.dk/~keld/research/LKH-3/) is a TSP/VRP solver written in C language, and [lkh](https://github.com/ben-hudson/pylkh) is its Python wrapper, please refer to [lkh](https://github.com/ben-hudson/pylkh) for more detail about the installation.



## Code Structure

The main code of the upper-level model structure and the TSP environment locate in `h_tsp.py`.
Details about the neural networks and other miscellaneous are in `rl_models.py` and `rl_utils.py`.

The deep reinforcement learning training is in `train.py`, while the code for evaluation is in `evaluate.py`.
The experiment hyperparameters are in `config_ppo.yaml`.

Codes of the lower model are in the `rl4cop` folder. Refer to `README` in the folder for more details.

## Basic Usage

### Evaluate

eval on tsp_random

```
# For TSP1000:
python eval.py --problem_size 1000 --dataset_path Dataset/random/tsp1000_test_concorde.txt --lkh_layer_number 2 
# For TSP2000:
python eval.py --problem_size 2000 --dataset_path Dataset/random/tsp2000_test_concorde.txt --lkh_layer_number 2 
# For TSP5000:
python eval.py --problem_size 5000 --dataset_path Dataset/random/tsp5000_test_concorde.txt --lkh_layer_number 3 
# For TSP10000:
python eval.py --problem_size 10000 --dataset_path Dataset/random/tsp10000_test_concorde.txt --lkh_layer_number 3
# For TSP20000:
python eval.py --problem_size 20000 --dataset_path Dataset/random/tsp20000_test_concorde.txt --lkh_layer_number 4 
# For TSP50000:
python eval.py --problem_size 50000 --dataset_path Dataset/random/tsp50000_test_concorde.txt --lkh_layer_number 4 
# For TSP100000:
python eval.py --problem_size 100000 --dataset_path Dataset/random/tsp100000_test_concorde.txt --lkh_layer_number 5 
```

### Train

train a model on TSP50.

```
python run.py --data_distribution scale --graph_size 50 --n_epochs 200
```
## Citation

If you find this work helpful, please consider cite our paper:

```
@inproceedings{zhou2025dualopt,
    author = {Zhou, Shipei and Ding, Yuandong and Zhang, Chi and Cao, Zhiguang and Jin, Yan},
    title = {DualOpt: A Dual Divide-and-Optimize Algorithm for the Large-scale Traveling
 Salesman Problem},
    booktitle = {AAAI 2025},
    year = {2025},
    month = {February},
    url = {https://arxiv.org/abs/2501.08565},
}
```


