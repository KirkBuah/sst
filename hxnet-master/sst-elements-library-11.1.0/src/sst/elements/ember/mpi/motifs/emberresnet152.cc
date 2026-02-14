#include <sst_config.h>
#include "emberresnet152.h"

using namespace SST::Ember;

#define COMPUTE_STEP 100

void EmberResNet152Generator::temp_fix_all_reduce_size(int idx) {

    int current = allreduce_sizes[idx]; 
    int min_div = 4 * size();
    int res = current / min_div;
    allreduce_sizes[idx] = res * min_div;

    return;
}

bool EmberResNet152Generator::generate_iteration(std::queue<EmberEvent *> &evQ)
{
    //printf("[%d] generate_iteration: m_i_b: %d; m_t_b: %d/%d\n", rank(), m_i_b, m_t_b, m_bwd_rt_per_B);
    if (m_i_b == 0)
    {
        // forward
        enQ_compute(evQ, m_fwd_rt_whole_model);
        count_compute_time += m_fwd_rt_whole_model;

        enQ_compute(evQ, m_bwd_rt_per_B);
        count_compute_time += m_bwd_rt_per_B;
    }

    // progress in-flight allreduces
    bool all_completed = true;
    for (auto &allreduce : m_allreduces)
        all_completed = all_completed && allreduce->progress(evQ);

    // backward
    if (m_i_b < NUM_B)
    {
        if (m_i_b == 0 || m_t_b >= m_bwd_rt_per_B)
        {
            printf("[%d] new allreduce: m_i_b: %d; size: %d\n", rank(), m_i_b, allreduce_sizes[m_i_b]);
            temp_fix_all_reduce_size(m_i_b);
            EmberRingAllreduce* new_allred;
            if (!all_reduce_type.compare("05D")) {
                new_allred = new EmberRingAllreduce05D(*this, allreduce_sizes[m_i_b], rank(), size(), GroupWorld, m_aggregation_cost_ns, true);
            } else if (!all_reduce_type.compare("2D")) {
                new_allred = new EmberRingAllreduce2D(*this, allreduce_sizes[m_i_b], rank(), size(), GroupWorld, m_aggregation_cost_ns, true, px);
            } else if (!all_reduce_type.compare("25D")) {
                new_allred = new EmberRingAllreduce25D(*this, allreduce_sizes[m_i_b], rank(), size(), GroupWorld, m_aggregation_cost_ns, true, px);
            } else {
                printf("Unexpected branch with all reduce type! Exiting!\n");
                exit(EXIT_FAILURE);
            }
            printf("Using %s All Reduce\n", all_reduce_type.c_str());

            // we need to progress it now otherwise simqueue becomes empty (also consisten with what an MPI_Iallreduce would do).
            new_allred->progress(evQ);

            m_allreduces.push_back(new_allred);

            m_i_b++;
            m_t_b = 0;
        }
        else
        {
            if (all_completed) {
                // there is nothing to progress -> fast forward
                enQ_compute(evQ, m_bwd_rt_per_B - m_t_b);
                count_compute_time += m_bwd_rt_per_B - m_t_b;
                printf("m_bwd_rt_per_B compute %d\n", m_bwd_rt_per_B - m_t_b); fflush(stdout);
                m_t_b = m_bwd_rt_per_B;
            } else {
                enQ_compute(evQ, COMPUTE_STEP);
                count_compute_time += COMPUTE_STEP;
                //printf("count_compute_time compute %d\n", COMPUTE_STEP); fflush(stdout);
                m_t_b += COMPUTE_STEP;
            }
        }

        return false;
    }
    else
    {
        return all_completed;
    }
}

bool EmberResNet152Generator::generate(std::queue<EmberEvent *> &evQ)
{
    //printf("[%d] m_iter: %d/%d\n", rank(), m_iter, RUNS);

    while (1) {
        if (m_iter >= RUNS) return true;
    
        bool it_complete = generate_iteration(evQ);
        if (it_complete)
        {
            printf("[%d] Iteration complete!\n", rank());
            m_i_b = 0;
            assert(m_t_b == 0);
            m_iter++;

            for (auto &allreduce : m_allreduces)
                delete allreduce;
            m_allreduces.clear();
            // loop back
        } else return false;
    }
}

EmberResNet152Generator::EmberResNet152Generator(SST::ComponentId_t id, Params &params)
    : EmberHxMeshGenerator(id, params, "ResNet152"), m_i_b(0), m_t_b(0), m_iter(0)
{
    m_aggregation_cost_ns = (double)params.find("arg.aggregation_cost_ns", 0.01);
    px = (uint32_t)params.find("arg.px", 0);
    
    // Check type of all reduce and if it is a valid one
    all_reduce_type = params.find<std::string>("arg.all_reduce_type", "05D");
    if (all_reduce_type.compare("05D") && all_reduce_type.compare("2D") && all_reduce_type.compare("25D")) {
        printf("Error, non valid all reduce type!\n"); 
        exit(EXIT_FAILURE);
    }

    // Change compute time based on total number of nodes
    switch(size()) {
        case 16:
            m_bwd_rt_per_B = 23800 * 1e3;        // ns
            m_fwd_rt_whole_model = 119000 * 1e3; // ns
            break;
        case 256:
            m_bwd_rt_per_B = 23800 * 1e3;        // ns
            m_fwd_rt_whole_model = 119000 * 1e3; // ns
            break;
        case 512:
            m_bwd_rt_per_B = 12600 * 1e3;        // ns
            m_fwd_rt_whole_model = 63000 * 1e3; // ns
            break;
        case 1024:
            m_bwd_rt_per_B = 7200 * 1e3;        // ns
            m_fwd_rt_whole_model = 36000 * 1e3; // ns
            break;
        case 2048:
            m_bwd_rt_per_B = 5533 * 1e3;        // ns
            m_fwd_rt_whole_model = 27667 * 1e3; // ns
            break;
        default:
            printf("Number of nodes not supported\n"); 
            exit(EXIT_FAILURE);
        }
}

EmberResNet152Generator::~EmberResNet152Generator()
{
    printf("\nRank %d - Total Compute time %" PRIu64 " \n", rank(), count_compute_time);
}