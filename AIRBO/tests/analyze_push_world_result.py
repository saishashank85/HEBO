"""
Analyze the history file generated by running RoBO in push world
"""
# %%
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from utils import commons as cm
from problems.robot_pushing import push_env as pe
from utils import visulaization as vis
from utils import input_uncertainty as iu
from model_utils import input_transform as itf


# %%
# load a result
opt_hist_dir = "./results/"
opt_hist_fns = [
    "E-TripleGoalsP3-GMMInputDistribution-0209090046/E-TripleGoalsP3-GMMInputDistribution-0209090046.hist",
]

opt_hist_results = {}
for hfn in opt_hist_fns:
    rn_suffix = hfn.split(".hist")[0].split("-")[-1]
    _r = cm.pickle_load(f"{opt_hist_dir}{hfn}")
    for k, v in _r.items():
        if k in opt_hist_results.keys():
            k += f"_{rn_suffix}"
        opt_hist_results[k] = v

save_dir = f"./results/push_world/"
cm.ensure_dir_exist(save_dir)
# %%
# env & mesh
env = pe.TripleGoalsP3Env()
opt_end_pos = np.array([3, 3]).reshape(-1, 2)
goals = env.get_goals()
model_names = ['M-GP', 'M-ERBF', 'M-skl', 'M-MMDGP', 'M-uGP']
x_range = (-6, 6)
y_range = (-6, 6)
cmap = plt.get_cmap('coolwarm_r')
mesh_X = np.arange(x_range[0], x_range[1], 0.1)
mesh_Y = np.arange(y_range[0], y_range[1], 0.1)
mesh_samp_num = len(mesh_X)
mesh_xx, mesh_yy = np.meshgrid(mesh_X, mesh_Y)
mesh_coords = np.stack([mesh_xx, mesh_yy], axis=-1)
mesh_vals = np.array(
    [env.compute_dist(env.get_goals(), e) for row in mesh_coords for e in row]
).reshape(len(mesh_X), len(mesh_Y))

# %%
# plot landscape
fig = plt.figure(figsize=(4 * 2 * 1.6, 3 * 1 * 1.6))
ax0 = fig.add_subplot(121)
pc = ax0.contourf(mesh_X, mesh_Y, mesh_vals, levels=20, cmap=cmap)
plt.colorbar(pc, ax=ax0)
ax1 = fig.add_subplot(122, projection='3d')
ax1.plot_surface(mesh_xx, mesh_yy, mesh_vals, cmap=cmap)
plt.tight_layout()
plt.show()

# %%
# plot the final end pos
min_cov = 1e-6
input_distrib = iu.GMMInputDistribution(
    n_components=2, mean=np.array([[0, 0, 0], [-1, 1, 0]]),
    covar=np.array([
        [0.1 ** 2, -0.3 ** 2, min_cov],
        [-0.3 ** 2, 0.1 ** 2, min_cov],
        [min_cov, min_cov, 1 ** 2.0],
    ]),
    covariance_type='tied',
    weight=np.array([0.5, 0.5])
)
for ax_i, m_name in enumerate(model_names):
    fig = plt.figure()
    ax = fig.add_subplot(111)
    # plot contour
    pc = ax.contourf(mesh_X, mesh_Y, mesh_vals, cmap=cmap)
    plt.colorbar(pc, ax=ax)

    # plot end positions
    m_hist_result = {k: v for k, v in opt_hist_results.items() if m_name in k}
    for m_hist in m_hist_result.values():
        outcome_x = m_hist[-1][-4].flatten()
        outcome_X = np.tile(outcome_x, reps=(50, 1))
        outcome_x_samples = itf.add_noise(
            X=outcome_X,
            sampling_func=input_distrib.sample,
            sampling_cfg={'x': outcome_X}
        )
        for ox in outcome_x_samples:
            goals, end_pos, dist = env.evaluate_ex(ox)
            rx, ry, rt = ox[:3]
            pe.plot_push_world(goals, end_pos, dist, rx, ry, rt, fig=fig, ax=ax,
                               plot_goals=True, plot_obj_init_pos=True, plot_obj_end_pos=True,
                               plot_robot_init_pos=True, plot_push_direction=True)
    ax.set_title(m_name)
    ax.set_xlim(x_range)
    ax.set_ylim(y_range)
    fig.tight_layout()
plt.show()

# %%
# collect the outcome_x of the last step and get the corresponding push results
push_results = {}
for m_name in model_names:
    m_hist_result = {k: v for k, v in opt_hist_results.items() if m_name in k}
    m_push_results = []
    push_results[m_name] = m_push_results
    for m_hist in m_hist_result.values():
        outcome_x = m_hist[-1][-4].flatten()
        goals, end_pos, dist = env.evaluate_ex(outcome_x)
        m_push_results.append((*outcome_x, end_pos[0], end_pos[1], float(dist)))

# %%
# compute the statistics for each quadrant
rt_cmap = plt.get_cmap('rainbow')
nrows, ncols, ax_scale = 1, len(model_names), 1.0
fig, axes = plt.subplots(nrows=nrows, ncols=ncols, squeeze=True,
                         figsize=(4 * ncols * ax_scale, 4 * nrows * ax_scale))
for m_i, m_name in enumerate(model_names):
    m_results = push_results[m_name]
    m_df = pd.DataFrame(
        m_results,
        columns=['r_pos_x', 'r_pos_y', 'rt', 'e_pos_x', 'e_pos_y', 'dist'] \
            if len(m_results[0]) == 6 \
            else ['r_pos_x', 'r_pos_y', 'rt', 'ra', 'e_pos_x', 'e_pos_y', 'dist']
    )
    disc = f"{m_name}, total={m_df.shape[0]}"
    # quadrants
    for q_name, q_cond in [
        # ("Q1",  (m_df['r_pos_x'] > 0) & (m_df['r_pos_y'] > 0)),
        ("Q2", (m_df['r_pos_x'] < 0) & (m_df['r_pos_y'] > 0)),
        ("Q3", (m_df['r_pos_x'] < 0) & (m_df['r_pos_y'] < 0)),
        ("Q4", (m_df['r_pos_x'] > 0) & (m_df['r_pos_y'] < 0)),
    ]:
        m_quadrant_df = m_df[q_cond]
        disc += f"\n [{q_name}] count:{m_quadrant_df.shape[0]}" \
                f"({m_quadrant_df.shape[0] * 100.0 / m_df.shape[0]:.2f}%), " \
                f"rt={m_quadrant_df['rt'].mean():.2f}+-{m_quadrant_df['rt'].std():.2f}"
        if 'ra' in m_quadrant_df.columns:
            disc += f", ra={m_quadrant_df['ra'].mean():.3f}+-{m_quadrant_df['ra'].std():.3f}"
        x_noise_range, y_noise_range = (-0.2, 0.2), (-0.2, 0.2)
        m_quadrant_df['r_pos_x'] += np.random.uniform(*x_noise_range, size=m_quadrant_df.shape[0])
        m_quadrant_df['r_pos_y'] += np.random.uniform(*y_noise_range, size=m_quadrant_df.shape[0])
        pc = axes[m_i].scatter(m_quadrant_df['r_pos_x'], m_quadrant_df['r_pos_y'],
                               marker='o', c=m_quadrant_df['rt'], alpha=0.5,
                               cmap=rt_cmap, vmin=15, vmax=30)
        pc.set_edgecolor("k")

    plt.colorbar(pc, ax=axes[m_i])
    axes[m_i].axvline(0, ls='--', lw=1, c='tab:grey', alpha=0.5)
    axes[m_i].axhline(0, ls='--', lw=1, c='tab:grey', alpha=0.5)
    axes[m_i].set_xlim(-5.5, 5.5)
    axes[m_i].set_ylim(-5.5, 5.5)
    axes[m_i].annotate("Q1", xy=(0+2.25, 0.1), xycoords='data')
    axes[m_i].annotate("Q2", xy=(0+2.25, -5.4), xycoords='data')
    axes[m_i].annotate("Q3", xy=(-5.5+2.25, -5.4), xycoords='data')
    axes[m_i].annotate("Q4", xy=(-5.5+2.25, 0.1), xycoords='data')
    axes[m_i].set_title(disc)
fig.tight_layout()
plt.show()

# %%
# compute regret
oracle_exact_opt_ind = None
oracle_exact_opt_x = None
oracle_exact_optimum = None
oracle_robust_opt_ind = None
oracle_robust_opt_x = None
oracle_robust_opt_end_pos = np.array([3, -3]).reshape(1, 2)
oracle_robust_optimum = None
converge_thr = oracle_exact_optimum

print("Computing the stats results")
STATS_REGRET = "Regret"
STATS_DIST_2_OPT = "Distance to optimum"
STATS_DIST_2_OPT_END_POS = "Distance to opt. end position"
selected_model_names = [
    'MMDGP-nystrom',
    'GP',
    'skl',
    'ERBF',
    'uGP',
]
model_zorders = {
        'GP': 10,
        'skl': 20,
        'ERBF': 30,
        'MMDGP-raw': 40,
        'uGP': 50,
        'MMDGP-nystrom': 60,
    }
stats_metrics = [
    (STATS_REGRET, -2),
    # (STATS_DIST_2_OPT, -3),
    # (STATS_DIST_2_OPT_END_POS, -1),
]
stats_results = {}
for s_name, s_val_ind in stats_metrics:
    trial_stats = {}
    for m_name in selected_model_names:
        m_trials = {k: r for k, r in opt_hist_results.items() if m_name in k}
        m_trial_stats = pd.concat(
            [
                pd.DataFrame([(h[0], h[s_val_ind]) for h in t_history],
                             columns=['step_i', s_name]).set_index('step_i')
                for t_history in m_trials.values()
            ],
            axis=1
        )
        if s_name == STATS_REGRET:
            m_trial_stats.ffill(inplace=True)
            m_trial_stats = m_trial_stats.cummin(axis=0)
            if oracle_exact_optimum is not None:
                m_trial_stats = m_trial_stats - oracle_robust_optimum
        elif s_name == STATS_DIST_2_OPT:
            m_trial_stats.ffill(inplace=True)
            m_trial_stats = m_trial_stats.applymap(
                lambda x: np.linalg.norm(
                    np.array(x).reshape(1, -1) - oracle_robust_opt_x.reshape(1, -1)
                )
            )
        elif s_name == STATS_DIST_2_OPT_END_POS:
            m_trial_stats.ffill(inplace=True)
            m_trial_stats = m_trial_stats.applymap(
                lambda x: np.linalg.norm(
                    np.array(x).reshape(1, -1) - oracle_robust_opt_end_pos.reshape(1, -1)
                )
            )
        else:
            raise ValueError("Unsupported stats name:", s_name)
        trial_stats[m_name] = m_trial_stats
    stats_results[s_name] = trial_stats

# visualize the stats
nrows, ncols, ax_scale = len(stats_results), 2, 1.0
fig, axes = plt.subplots(
    nrows, ncols, squeeze=False, figsize=(4 * ncols * ax_scale, 3 * nrows * ax_scale), sharex=True
)
# axes = axes.flatten()
for s_i, (s_name, stat_result) in enumerate(stats_results.items()):
    for i, (m_name, m_stat) in enumerate(stat_result.items()):
        _x = m_stat.index.values
        _mean = m_stat.mean(axis=1)
        _std = m_stat.std(axis=1)
        _ucb = _mean + _std * 2.0
        _lcb = _mean - _std * 2.0
        _zo = model_zorders[m_name]
        axes[s_i, 0].plot(_x, _mean, label=f'{m_name}', **{**vis.LINE_STYLES[i + 1], 'alpha': 1.0,
                                                        'zorder': _zo})
        axes[s_i, 1].plot(_x, _std, label=f'{m_name}', **{**vis.LINE_STYLES[i + 1], 'alpha': 1.0,
                                                           'zorder': _zo})
        # axes[s_i].fill_between(_x, _lcb, _ucb, **{**vis.AREA_STYLE[i + 1], 'alpha': 0.3,
        #                                           'zorder': _zo})

    axes[s_i, 0].set_xlabel('step')
    axes[s_i, 1].set_xlabel('step')
    axes[s_i, 0].set_xlim(0, _x.max())
    axes[s_i, 1].set_xlim(0, _x.max())
    axes[s_i, 0].set_ylabel(f"{s_name}(mean)")
    axes[s_i, 1].set_ylabel(f"{s_name}(std)")
    axes[s_i, 0].legend(ncol=2)
    axes[s_i, 1].legend(ncol=2)
fig.tight_layout()
vis_fp = f"{save_dir}push_world_result.png"
plt.savefig(vis_fp)
print("done, result visualization is saved at", vis_fp)