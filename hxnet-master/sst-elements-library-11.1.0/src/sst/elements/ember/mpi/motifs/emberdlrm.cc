#include <sst_config.h>
#include "emberdlrm.h"

using namespace SST::Ember;

#define BOT_MLP_SIZE   49536
#define TOP_MLP_SIZE   728064 
#define EMB_ALL2ALL_SIZE   262144  //2048*128

// runtime in us (10E-6)
#define FWD_BOT_MLP (341*1000)
#define FWD_TOP_MLP (455*1000)
#define FWD_INTER (209*1000)
#define FWD_EMB (95*1000)

#define COMPUTE_STEP 100

bool EmberDLRMGenerator::generate(std::queue<EmberEvent *> &evQ)
{
    switch(m_state)
    {
    case FWD:
    {
        enQ_compute(evQ, FWD_EMB);
        count_compute_time += FWD_EMB;
        m_state = ALLTOALL_1;
        // no break
    }
    case ALLTOALL_1:
    {
        if (!m_alltoall1->progress(evQ)) return false;
        m_state = FWDBWD;
        // no break
    }
    case FWDBWD:
    {
        enQ_compute(evQ, FWD_BOT_MLP);
        enQ_compute(evQ, FWD_INTER);
        enQ_compute(evQ, FWD_TOP_MLP);
        enQ_compute(evQ, FWD_TOP_MLP*2);
        count_compute_time += FWD_BOT_MLP;
        count_compute_time += FWD_INTER;
        count_compute_time += FWD_TOP_MLP;
        count_compute_time += FWD_TOP_MLP*2;
        m_state = ALLREDUCE;
        // no break
    }
    case ALLREDUCE:
    {
        bool allreduce_completed = m_allreduce1->progress(evQ);
        bool comp_left = m_comp_overlap < (FWD_INTER + FWD_BOT_MLP*2);

        if (comp_left) {
            enQ_compute(evQ, COMPUTE_STEP);
            count_compute_time += COMPUTE_STEP;
            m_comp_overlap += COMPUTE_STEP;
        }
        
        if (!allreduce_completed) return false;

        comp_left = m_comp_overlap < (FWD_INTER + FWD_BOT_MLP*2);
        
        if (comp_left) { 
            // fast forward
            enQ_compute(evQ, (FWD_INTER + FWD_BOT_MLP*2) - m_comp_overlap);
            count_compute_time += (FWD_INTER + FWD_BOT_MLP*2) - m_comp_overlap;
            m_comp_overlap = FWD_INTER + FWD_BOT_MLP*2;
        }

        m_state = ALLRED_ALLTOALL;
        // no break
    }
    case ALLRED_ALLTOALL:
    {
        if (m_progress_allreduce_2) {
            bool allred2_completed = m_allreduce2->progress(evQ);
            m_progress_allreduce_2 = !allred2_completed;
        }

        if (m_progress_alltoall_2) {
            bool alltoall2_completed = m_alltoall2->progress(evQ);
            m_progress_alltoall_2 = !alltoall2_completed;
        }

        if (m_progress_allreduce_2 || m_progress_alltoall_2) return false;
        return true;
    }
    default: assert(0);
    }

    assert(0);
}


EmberDLRMGenerator::EmberDLRMGenerator(SST::ComponentId_t id, Params &params)
    : EmberHxMeshGenerator(id, params, "DLRM"), m_progress_allreduce_2(true), m_progress_alltoall_2(true), m_state(FWD), m_comp_overlap(0)
{
    m_aggregation_cost_ns = (double)params.find("arg.aggregation_cost_ns", 0.01);
    px = (uint32_t)params.find("arg.px", 0);
    
    // Check type of all reduce and if it is a valid one
    all_reduce_type = params.find<std::string>("arg.all_reduce_type", "05D");
    if (all_reduce_type.compare("05D") && all_reduce_type.compare("2D") && all_reduce_type.compare("25D")  && all_reduce_type.compare("2DRev")) {
        printf("Error, non valid all reduce type!\n"); 
        exit(EXIT_FAILURE);
    }

    if (!all_reduce_type.compare("05D")) {
        m_allreduce1 = new EmberRingAllreduce05D(*this, TOP_MLP_SIZE, rank(), size(), GroupWorld, m_aggregation_cost_ns, true);
        m_allreduce2 = new EmberRingAllreduce05D(*this, BOT_MLP_SIZE, rank(), size(), GroupWorld, m_aggregation_cost_ns, true);
    } else if (!all_reduce_type.compare("2D")) {
        m_allreduce1 = new EmberRingAllreduce2D(*this, TOP_MLP_SIZE, rank(), size(), GroupWorld, m_aggregation_cost_ns, true, px);
        m_allreduce2 = new EmberRingAllreduce2D(*this, BOT_MLP_SIZE, rank(), size(), GroupWorld, m_aggregation_cost_ns, true, px);
    } else if (!all_reduce_type.compare("2DRev")) {
        m_allreduce1 = new EmberRingAllreduceRev(*this, TOP_MLP_SIZE, rank(), size(), GroupWorld, m_aggregation_cost_ns, true, px);
        m_allreduce2 = new EmberRingAllreduceRev(*this, BOT_MLP_SIZE, rank(), size(), GroupWorld, m_aggregation_cost_ns, true, px);
    } else if (!all_reduce_type.compare("25D")) {
        m_allreduce1 = new EmberRingAllreduce25D(*this, TOP_MLP_SIZE, rank(), size(), GroupWorld, m_aggregation_cost_ns, true, px);
        m_allreduce2 = new EmberRingAllreduce25D(*this, BOT_MLP_SIZE, rank(), size(), GroupWorld, m_aggregation_cost_ns, true, px);
    } else {
        printf("Unexpected branch with all reduce type! Exiting!\n");
        exit(EXIT_FAILURE);
    }
    printf("Using %s All Reduce\n", all_reduce_type.c_str());

    m_alltoall1 = new EmberImprovedAlltoall(*this, EMB_ALL2ALL_SIZE/size(), rank(), size(), GroupWorld);
    m_alltoall2 = new EmberImprovedAlltoall(*this, EMB_ALL2ALL_SIZE/size(), rank(), size(), GroupWorld);
}

EmberDLRMGenerator::~EmberDLRMGenerator()
{
    delete m_alltoall1;
    delete m_alltoall2;
    delete m_allreduce1;
    delete m_allreduce2;
    printf("\nRank %d - Total Compute time %" PRIu64 " \n", rank(), count_compute_time);
}