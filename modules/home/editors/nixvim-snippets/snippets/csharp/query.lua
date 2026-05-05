return {
  trig = "dddquery",
  name = "DDD query and handler",
  desc = "MediatR query with request and handler",
  template = [[
public sealed record {{Action}}{{Feature}}Query({{Args}}) : IRequest<{{Response}}>;

public sealed class {{Action}}{{Feature}}QueryHandler({{Dependency}})
    : IRequestHandler<{{Action}}{{Feature}}Query, {{Response}}>
{
    public async Task<{{Response}}> Handle({{Action}}{{Feature}}Query request, CancellationToken ct)
    {
        throw new NotImplementedException();
    }
}
]],
}
