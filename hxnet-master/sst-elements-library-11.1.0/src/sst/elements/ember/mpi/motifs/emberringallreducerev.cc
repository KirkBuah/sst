#include <sst_config.h>
#include "emberringallreducerev.h"

using namespace SST::Ember;

EmberRingAllreduceRevGenerator::EmberRingAllreduceRevGenerator(SST::ComponentId_t id, Params &params) 
: EmberHxMeshGenerator(id, params, "RingAllreduceRev")
{
    double aggregation_cost_ns = (double)params.find("arg.aggregation_cost_ns", 0.01);
    uint32_t count = (uint32_t)params.find("arg.count", 1);
    bool blocking = (bool)params.find("arg.blocking", true);
    uint32_t concurrent = (uint32_t)params.find("arg.concurrent", 1);
    uint32_t px = (uint32_t)params.find("arg.px", 0);

    
    for (int i=0; i<concurrent; i++){
        m_allreduce.push_back(new EmberRingAllreduceRev(*this, count, rank(), size(), GroupWorld, aggregation_cost_ns, !blocking, px));
    }
}

EmberRingAllreduceRevGenerator::~EmberRingAllreduceRevGenerator()
{
    for (auto allreduce_ptr : m_allreduce) 
    {
        allreduce_ptr->printStats();
        delete allreduce_ptr;
    }
}

bool EmberRingAllreduceRevGenerator::generate(std::queue<EmberEvent *> &evQ)
{
    bool allcompleted = true;
    for (auto allreduce_ptr : m_allreduce) {
        if (!allreduce_ptr->progress(evQ)) allcompleted = false;
    }
    return allcompleted;
}