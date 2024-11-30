from django.core.paginator import Paginator
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.shortcuts import render, redirect, get_object_or_404
from django.db.models.manager import BaseManager
from django.db.models import Count, Q
from django.views.decorators.http import require_POST
from django.views.generic.edit import CreateView
from django.urls import reverse_lazy
from .forms import PostForm, CommentForm, ProfileEditForm
from .models import Category, Post, Comment
from datetime import datetime, timezone


PER_PAGE = 10


# Create your views here.
class RegisterView(CreateView):
    template_name = 'registration/registration_form.html'
    form_class = UserCreationForm
    success_url = reverse_lazy('blog:index')


def profile_view(request, username):

    profile = get_object_or_404(User, username=username)

    posts = Post.objects.select_related(
        'location', 'author', 'category'
    ).filter(
        author=profile.pk
    ).annotate(
        comment_count=Count("comments")
    ).order_by(
        "-pub_date"
    )
    page_obj = Paginator(posts, PER_PAGE)
    page_obj = page_obj.get_page(request.GET.get('page'))

    return render(request, 'blog/profile.html',
                  {'profile': profile,
                   'page_obj': page_obj})


@login_required
def edit_profile_view(request):

    form = ProfileEditForm(instance=request.user)

    if request.method == 'POST':
        form = ProfileEditForm(request.POST)

        if form.is_valid():
            user = User.objects.get(pk=request.user.pk)

            user.first_name = form.cleaned_data["first_name"]
            user.last_name = form.cleaned_data["last_name"]
            user.email = form.cleaned_data["email"]

            user.save()

    context = {
        "form": form
    }

    return render(request, 'blog/user.html', context)


def index(request):

    posts = _filter_posts(Post.objects.select_related(
        'location', 'author', 'category'
    ))
    page_obj = Paginator(posts, PER_PAGE)
    page_obj = page_obj.get_page(request.GET.get('page'))

    return render(request, 'blog/index.html',
                  {'page_obj': page_obj})


def post_detail(request, post_id):

    now = datetime.now(timezone.utc)
    post_obj = get_object_or_404(
        Post,
        Q(
            pk=post_id,
            pub_date__lte=now,
            category__is_published=True,
            is_published=True
        ) | Q(
            pk=post_id,
            author=request.user
        )
    )
    comments = Comment.objects.filter(post=post_obj)
    context = {
        'post': post_obj,
        'form': CommentForm(),
        'comments': comments
    }

    return render(request, 'blog/detail.html', context)


def category_posts(request, category_slug):

    category_obj = get_object_or_404(
        Category,
        slug=category_slug,
        is_published=True
    )
    posts = _filter_posts(category_obj.posts.select_related(
        'location', 'author', 'category'
    ),
        category_filtered=True
    )
    page_obj = Paginator(posts, PER_PAGE)
    page_obj = page_obj.get_page(request.GET.get('page'))

    return render(request, 'blog/category.html', {
        'page_obj': page_obj,
        'category': category_obj}
    )


@login_required
def post_create_view(request):

    post = PostForm()
    if request.method == 'POST':
        post = PostForm(request.POST, request.FILES)

        if post.is_valid():
            post_instance = post.save(commit=False)
            post_instance.author = request.user
            post_instance.save()

            user = post_instance.author.username
            return redirect("blog:profile", username=user)

    context = {
        "form": post
    }

    return render(request, "blog/create.html", context=context)


@login_required
def post_edit_view(request, post_id):

    post = get_object_or_404(
        Post,
        pk=post_id
    )

    if request.method == 'POST':

        post_form = PostForm(request.POST, request.FILES)
        if request.user.pk == post.author.pk:

            if post_form.is_valid():
                post.text = post_form.cleaned_data["text"]
                post.title = post_form.cleaned_data["title"]
                post.pub_date = post_form.cleaned_data["pub_date"]
                post.category = post_form.cleaned_data["category"]
                post.location = post_form.cleaned_data["location"]

                post.save()

        return redirect("blog:post_detail", post_id=post_id)

    else:
        post_form = PostForm(instance=post)

        context = {
            "form": post_form
        }

        return render(request, "blog/create.html", context=context)


@login_required
def post_delete_view(request, post_id):

    post = get_object_or_404(
        Post,
        pk=post_id
    )
    if request.user.pk != post.author.pk:
        return redirect("blog:post_detail", post_id=post_id)

    else:
        user = post.author.username
        post.delete()

        return redirect("blog:profile", username=user)


@login_required
@require_POST
def comment_create_view(request, post_id):

    post = get_object_or_404(
        Post,
        pk=post_id
    )
    comment = CommentForm(request.POST)

    if comment.is_valid():
        comment_instance = comment.save(commit=False)
        comment_instance.author = request.user
        comment_instance.post = post

        comment_instance.save()

    return redirect("blog:post_detail", post_id=post_id)


@login_required
def comment_edit_view(request, post_id, comment_id):

    comment = get_object_or_404(
        Comment,
        pk=comment_id
    )

    if request.method == 'POST':

        comment_form = CommentForm(request.POST)
        if request.user.pk == comment.author.pk:

            if comment_form.is_valid():
                comment.text = comment_form.cleaned_data["text"]
                comment.save()

        return redirect("blog:post_detail", post_id=post_id)

    else:
        comment_form = CommentForm(instance=comment)
        context = {
            "form": comment_form,
            "comment": comment
        }

        return render(request, "blog/comment.html", context)


@login_required
def comment_delete_view(request, post_id, comment_id):

    comment = get_object_or_404(
        Comment,
        pk=comment_id
    )
    if request.method == 'POST':

        if request.user.pk == comment.author.pk:
            comment.delete()

        return redirect("blog:post_detail", post_id=post_id)

    else:
        context = {
            "comment": comment
        }

        return render(request, "blog/comment.html", context)


def _filter_posts(posts: BaseManager[Post],
                  category_filtered=False) -> BaseManager[Post]:

    now = datetime.now(timezone.utc)
    posts = posts.annotate(
        comment_count=Count("comments")
    ).order_by(
        "-pub_date"
    )

    if category_filtered:
        return posts.filter(
            pub_date__lte=now,
            is_published=True
        )
    else:
        return posts.filter(
            pub_date__lte=now,
            is_published=True,
            category__is_published=True
        )
