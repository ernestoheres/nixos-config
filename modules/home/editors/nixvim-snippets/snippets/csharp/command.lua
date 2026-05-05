return {
  trig = "dddcommand",
  name = "DDD command and handler",
  desc = "MediatR command with request and handler",
  template = [[
public sealed record {{Action}}{{Feature}}Command({{Args}}) : IRequest<{{Response}}>;

public sealed class {{Action}}{{Feature}}CommandHandler({{Dependency}})
    : IRequestHandler<{{Action}}{{Feature}}Command, {{Response}}>
{
    public async Task<{{Response}}> Handle({{Action}}{{Feature}}Command request, CancellationToken ct)
    {
        throw new NotImplementedException();
    }
}
]],
}
